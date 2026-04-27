# PDF2PPT Pipeline 技术经验教训

## 概述

PDF2PPT 是将 PDF 文档转换为可编辑 PPTX 的自动化 pipeline。核心链路：`PDF → MinerU → Presentation → PPT`。本文档总结实现过程中的关键技术决策、踩坑经验与最佳实践。

---

## 架构决策

### 为什么用 MinerU 而非 PyMuPDF？

**初始想法**：用 PyMuPDF 直接提取 PDF 文字/图片，成本低。

**实际问题**：
- PyMuPDF 无法处理扫描件/OCR 内容
- 复杂排版（多栏、图文混排）解析混乱
- 缺少语义信息（标题/正文/图片分类）

**最终决策**：完全依赖 MinerU 服务
- 提供 `middle.json`（几何信息）+ `content_list.json`（语义分类）
- 支持 OCR 和版面分析
- API 调用模式，与 pipeline 解耦

**教训**：选工具时先看**最坏情况能否处理**，别只看 sunny-day case。

---

### Artifact 解析策略：middle.json vs content_list.json

| 文件 | 用途 | 可靠性 |
|------|------|--------|
| `*_middle.json` | 几何 bbox、行级文本 | 必须，fallback 首选 |
| `*_content_list.json` | 语义分类（标题/正文） | 可选，增强用 |

**关键修正**：
- 早期：两者缺一不可，缺少任一直接报错
- 修正后：`middle.json` 可独立工作，语义分类降级为启发式规则

**教训**：外部依赖要设计**优雅降级**，别做成 all-or-nothing。

---

### Text Rendering 模式设计

**问题**：同样多行文本，title 和 body 渲染方式该一样吗？

| 元素类型 | 渲染策略 | 原因 |
|----------|----------|------|
| title, subtitle, caption | 每行一个 paragraph | 字号/位置差异大，需要精细控制 |
| body | 单 paragraph，软换行 | 行高一致，整体块移动 |

**技术细节**：
```python
# python-pptx 中换行语义
\n  -> 新 paragraph（自动创建）
\v  -> soft line break（同 paragraph）

# 实现
if should_render_lines_as_paragraphs:
    # 每行一个 paragraph
    for line in line_texts:
        p = tf.add_paragraph()
        p.text = line
else:
    # body 保持单 paragraph
    tf.text = content.replace("\n", "\v")
```

**教训**：
- `python-pptx` 换行符有坑，`\n` 和 `\v` 语义完全不同
- 设计时要考虑下游库的行为特性，别假设"理所当然"

---

## 踩坑实录

### 坑 1: Output Folder 误选旧产物

**现象**：新上传的 PDF 解析结果异常，混入旧文件内容。

**根因**：`_resolve_output_folder` 在无匹配候选时，用 `rglob` 全局搜 `*_middle.json`，可能捡到历史残留。

**修复**：
```python
if request_id:
    # request-scoped 场景，找不到就 None，绝不 fallback
    return None
# 只有非 request 场景才用宽泛搜索
```

**教训**：request-scoped 任务要有**严格边界**，禁止逃逸到全局搜索。

---

### 坑 2: RuntimeError 信息丢失

**现象**：MinerU 崩溃，review 状态只显示 "Mineru processing failed"，无具体错误。

**根因**：异常捕获时只传 message，没保留原始 `str(exc)`。

**修复**：
```python
except RuntimeError as exc:
    _mark_review_status(
        request_id, 
        "failed", 
        "conversion", 
        "Mineru processing failed",
        str(exc)  # 保留原始信息
    )
```

**教训**：错误处理要保留**完整上下文**，方便后期排查。

---

### 坑 3: FastAPI on_event 废弃

**现象**：启动时大量 DeprecationWarning。

**修复**：迁移到 `lifespan`：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(ensure_mineru_api_ready)
    try:
        yield
    finally:
        await asyncio.to_thread(shutdown_mineru_api)

app = FastAPI(..., lifespan=lifespan)
```

**教训**：依赖库升级要关注 deprecation，别等强制移除再修。

---

## 测试策略

### 回归测试设计原则

| 场景 | 测试文件 | 验证点 |
|------|----------|--------|
| middle-only 解析 | `test_parser.py` | 无 content_list.json 也能工作 |
| 多行 title 渲染 | `test_ppt_gen.py` | 生成多 paragraph |
| 多行 body 渲染 | `test_ppt_gen.py` | 单 paragraph，软换行 |
| artifact 归属 | `test_mineru_service.py` | request-scoped 不误捞 |
| error 信息保留 | `test_main.py` | RuntimeError 详情持久化 |
| output_root 一致 | `test_main.py` | `/upload` 使用 request-scoped 路径 |

**关键决策**：用真实文件 + python-pptx 读取验证，不做 mock。

**教训**：
- 对文件格式转换工具，mock 等于自欺欺人
- 真实文件测试慢，但必须做， catches format-specific bugs

---

### 测试执行

```bash
# 运行核心回归
uv run python -m pytest tests/test_mineru_service.py \
    tests/test_ppt_gen.py \
    tests/test_parser.py \
    tests/test_main.py \
    tests/test_real_pipeline.py
```

当前状态：
- **13 passed, 0 failed**
- 耗时：~170s（含真实 PDF 处理）

---

## API 集成经验

### MinerU 持久服务 vs 子进程

**对比**：

| 方案 | 启动时间 | 资源占用 | 并发 | 稳定性 |
|------|----------|----------|------|--------|
| 每次 spawn 子进程 | 慢（模型加载） | 用完即释 | 串行 | 一般 |
| 持久 API 服务 | 一次启动 | 常驻内存 | 可并发 | 更好 |

**当前选择**：FastAPI + subprocess 托管 MinerU API

**配置参数**：
```python
MINERU_API_HOST = "127.0.0.1"
MINERU_API_PORT = 8001
MINERU_API_AUTO_START = true
MINERU_API_TIMEOUT_SECONDS = 600
```

**教训**：
- 模型加载类服务，持久化比反复 spawn 省时间
- 做好健康检查 (`/health`) 和优雅关闭

---

### Multipart 文件上传

MinerU API 要求 `multipart/form-data`，手写请求注意 boundary：

```python
def _multipart_field(name: str, value: str, boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")

# 必须字段
fields = [
    ("output_dir", str(output_path)),
    ("backend", settings.MINERU_API_BACKEND),
    ("parse_method", settings.MINERU_API_PARSE_METHOD),
    ("return_md", "false"),
    ("return_middle_json", "true"),
    ("return_content_list", "true"),
]
```

**教训**：HTTP 客户端库若不支持自定义 multipart，手写时要严格遵循 RFC，注意 `\r\n` 细节。

---

## 代码质量 checklist

- [x] **Pipeline 一致性**：output_root 全程 request-scoped
- [x] **Artifact 归属**：request-scoped 场景禁止全局 fallback
- [x] **Error 信息**：保留原始异常详情
- [x] **Multiline 渲染**：title 多 paragraph，body 单 paragraph
- [x] **Deprecated API**：`on_event` → `lifespan`
- [x] **Docstring**：与实现同步
- [ ] **F7 遗留**：comment/stale 文档（低优先级）
- [ ] **F8 遗留**：main.py 过重（未来拆分）

---

## 未来改进方向

1. **字号映射精细化**：当前从 bbox 高度估算，可考虑字符级 font size 提取
2. **颜色保留**：MinerU 未输出颜色，需探索其他方案
3. **布局更精准**：考虑字符级 bbox 对齐，而非仅 textbox 级
4. **性能优化**：MinerU 调用是瓶颈，考虑异步批处理

---

## B1. Pipeline loss map

### 总览

```text
PDF 原文
  -> MinerU 结构化抽取
  -> parser_service.py 语义重建
  -> ppt_gen_service.py PPT 复排
  -> PowerPoint 最终渲染
```

**核心判断**：损失不是单点发生，而是**逐层累积**。

### 逐层 loss map

| 阶段 | 主要输入 | 主要损失 | 典型症状 | 主要责任点 | 可控杠杆 |
|------|----------|----------|----------|------------|----------|
| PDF -> MinerU | 页面像素、字体、绘制顺序 | glyph 级信息丢失、原始字体度量丢失 | 文字大小、字重、间距与源文档不一致 | MinerU OCR / layout | 控制是否走 editable，必要时 image_fallback |
| MinerU -> middle/content | block / line / span | 行边界、阅读顺序、语义分类近似化 | 标题/正文混淆、换行错位 | MinerU 输出格式本身 | 保留 line 级 bbox，少做二次合并 |
| middle/content -> Presentation | 结构化 JSON | block 合并、role 推断、字号估算 | 文本块被吞并、段落边界消失 | `parser_service.py` | `_merge_text_elements` 收敛阈值，保 line 结构 |
| Presentation -> PPTX | slide + element 模型 | textbox 自动排版、margin / wrap / anchor 重写 | 位置漂移、换行异常、标题/正文表现不一致 | `ppt_gen_service.py` | 固定 textbox 属性，按角色分渲染策略 |
| PPTX -> PowerPoint 展示 | 已生成 pptx | 字体替换、主题样式、Office 自动修正 | 打开后再度变形 | PowerPoint 本体 | 减少可变样式，避免依赖默认主题 |

### 代码级 loss 点

#### 1) `app/services/parser_service.py`

- **_merge_text_elements**
  - 会把相邻文本块合并成一个元素
  - 好处：减少碎片
  - 风险：吞掉真实换行、分栏、局部对齐信息
- **角色推断**
  - `semantic_role` 和 `text_level` 是启发式结果
  - 一旦误判，后续渲染策略直接选错
- **字号估算**
  - 主要依赖 bbox 高度
  - 对不同字体、缩放、压缩率只是近似

#### 2) `app/services/ppt_gen_service.py`

- **textbox 默认行为**
  - PowerPoint 会自动处理 margin、wrap、auto size
  - 不显式锁死就会二次改写布局
- **段落策略**
  - title/subtitle/caption 用 paragraph 级更接近原稿视觉
  - body 用单 paragraph + soft break 更稳
- **渲染模式**
  - `auto` 的启发式一旦偏了，就会在整页层面放大误差

#### 3) `app/main.py`

- **pipeline 入口**
  - 决定 request-scoped output_root、render_mode、review 状态
  - 入口策略错，后面所有步骤都在错误前提上工作
- **错误传播**
  - 只保留短消息时，后面无法判断是 MinerU、parser 还是 PPT 生成失败

### 直接结论

- **最容易丢保真**：`Presentation -> PPTX`
- **最容易丢语义**：`MinerU JSON -> Presentation`
- **最容易放大错误**：`render_mode` 选错
- **最容易造成慢**：MinerU OCR / layout + 大量 shape 构建

---

## B2. Fast / stable strategy

### 目标

把页面分成两类：

- **Fast path**：优先速度，允许少量版式损失
- **Stable path**：优先保真，接受更高成本

### 路由原则

| 页面特征 | 建议模式 | 目的 | 代价 |
|----------|----------|------|------|
| PPT-like、标题页、结构简单 | `editable` | 保留可编辑文本 | 速度中等，版式更细碎 |
| 多图、表格密集、混排复杂 | `image_fallback` | 最大化外观一致性 | 不可编辑，文件更大 |
| 头图 + 少量文本 | `hybrid_overlay` | 图像保真 + 关键文本可改 | 实现复杂，渲染更慢 |
| 纯文档页、正文为主 | `editable` 或 `auto` | 保持文本可编辑 | 需严格控制 textbox 行为 |

### 推荐判定规则

1. **先看 page archetype**
   - title slide
   - text-heavy slide
   - image/table heavy slide
   - mixed infographic slide

2. **再看结构复杂度**
   - 文本框数量高
   - 图像 / 表格占比高
   - 多栏 / 多块 / 不规则分布

3. **最后选渲染模式**
   - 简单页 -> `editable`
   - 复杂页 -> `image_fallback`
   - 需要两者兼得 -> `hybrid_overlay`

### 决策树

```text
page archetype simple?
  yes -> editable
  no
    complex visual blocks?
      yes -> image_fallback
      no
        important text needs editability?
          yes -> hybrid_overlay
          no -> image_fallback
```

### 稳定性优先的默认策略

- **title 页**：`editable`
- **正文密集页**：`editable`
- **图文混排页**：`hybrid_overlay`
- **信息图 / 海报 / 高密度视觉页**：`image_fallback`

### 速度优先的默认策略

- **默认关闭 LLM**
- **减少 shape 数量**
- **少分 paragraph，少拆 textbox**
- **能 image_fallback 的页直接 fallback**

### 实操结论

- 如果目标是**保真**，不要强迫所有页都 editable
- 如果目标是**速度**，不要把所有页都拆成细粒度文本框
- 最优解通常是 **按页分流**，不是全局固定一种模式

---

## 总结

PDF2PPT pipeline 的核心挑战：**外部依赖（MinerU）+ 格式转换（PDF↔PPTX）+ 保真度（位置/字号/语义）**。

**最关键的三条**：
1. **优雅降级**：middle.json 可独立工作，不依赖 content_list.json
2. **严格边界**：request-scoped 绝不 fallback 到全局搜索
3. **真实测试**：用 python-pptx 读取验证输出，不用 mock

---

*文档版本: 2025-01*
*维护: 当 pipeline 行为或 MinerU 接口变更时更新*
