# OpenClaw PPT Fidelity Lessons

## 1. 先查真实产物，不要只看分数
- 高 fidelity 总分不等于视觉正确。
- 必须检查实际生成的 PPTX：文本是否变形、是否缺字、是否错位、是否有重叠。
- 真实回归要覆盖“解析结果 -> 生成结果 -> PPT XML/shape 级别”的整条链路。

## 2. 缓存命中顺序会直接改变结果
- MinerU 输出目录里可能同时存在根目录缓存和子目录缓存。
- 先命中哪个目录，可能决定文本内容是否一致。
- 缓存选择必须稳定、可解释，优先返回最可信的原始解析产物，避免误用派生目录。

## 3. 小范围特判容易伤泛化
- 针对某一页或某一类 slide 的字号、对齐、颜色强制覆盖，短期可提分，长期容易制造新问题。
- 例如短标签居中、字号放大这类规则，若没有充分证据，最好去掉或收敛为更保守的通用逻辑。
- 通用渲染优先，特判只保留在可证明稳定的场景。

## 4. 文本问题要分清“解析错”还是“渲染错”
- 先对比 MinerU 原文、parser 输出、PPT shape 文本、PPT XML。
- 如果原始解析已经是错的，问题在 OCR/解析或缓存。
- 如果解析是对的但 PPT 错了，问题在生成链路或写入逻辑。

## 5. 必须做页级回归门禁
- 只看整体分数不够。
- 每页都要有最低门槛，例如 `>= 90`。
- 单页低分往往会被平均值掩盖，但用户肉眼最容易看到。

## 6. 调试要用最小复现
- 用单页、单元素、单 slide 的最小输入快速验证假设。
- 先隔离变量，再下结论。
- 例如先单独验证 `AI` 字符是否在生成阶段被改写，再决定是否修 parser 或 generator。

## 7. 生成链路要避免隐式污染
- 解析对象、生成对象、缓存对象不要共享可变状态。
- 任何原地修改都可能把后续 slide 一起污染。
- 深拷贝或只读传递更安全。

## 8. 回归测试要走真实链路
- 不要只 mock 解析或只 mock 生成。
- 最好用真实 PDF、真实 MinerU 输出、真实 PPTX 文件进行验证。
- 这样才能发现目录命中、文本编码、版式压缩这类端到端问题。

## 9. 处理文本时要保留可编辑性
- OCR 文本应尽量以可编辑 text box 方式保留。
- 不要为追求一致性而退化成整页截图。
- 图片、表格、文本三类元素要分别处理，避免互相污染。

## 10. Debug 顺序
- 先确认原始解析是否正确。
- 再确认 parser 是否改写内容。
- 再确认 PPT 生成是否改写内容。
- 最后看布局是否导致视觉错觉。

## Outcome
- 本次问题的关键经验是：**缓存目录选择和页级特判，都会直接影响 fidelity 与视觉正确性**。
- 以后优先用稳定解析源 + 通用渲染 + 页级回归门禁。

## 11. 临时调试文件怎么处理
- 大多数 `tmp_*` 文件是一次性诊断脚本，**不应长期留在主路径**。
- 真正有价值的内容要抽成三类：
  - 可复用的回归检查脚本
  - 可复用的故障定位结论
  - 可写入 lessons 的通用经验

### 值得保留的内容
- `tmp_regen_from_cache.py` / `tmp_fidelity_score.py`
  - 价值：稳定复用 MinerU 缓存，跑真实链路回归。
  - 可提炼：缓存回放 + fidelity 打分是固定回归入口。
- `tmp_overlap_audit.py` / `tmp_overlap_latest_pptx.py` / `tmp_text_overflow_audit2.py`
  - 价值：量化文本重叠、溢出、bbox 失配。
  - 可提炼：布局问题要用 shape 级度量，不要只肉眼看图。
- `tmp_compare_output_folders.py` / `tmp_compare_slide4_xml.py` / `tmp_find_threshold_ai_bug.py`
  - 价值：定位 `openclaw` 问题来自缓存目录选择，不是单纯生成器。
  - 可提炼：缓存根目录优先级会改变最终文本内容。
- `tmp_parser_codepoints_slide4.py` / `tmp_ai_exact_repro.py` / `tmp_ai_prefix_repro.py`
  - 价值：证明 `AI -> Al` 不是随机渲染噪声，而是解析/缓存链路里的稳定差异。
  - 可提炼：文本错位、缺字要先比对原始解析与生成文本的 codepoints。

### 适合降级为 deprecated/删除的内容
- 大量 `tmp_inspect_*`、`tmp_debug_*`、`tmp_ai_roundtrip.py` 这类一次性观察脚本。
- 只在当次排障中有意义，后续除非对应问题还会反复出现，否则不应保留在主工作区。

### 处理原则
- 能写进正式测试的，优先写成 `backend/tests/`。
- 只能辅助排障的，保留在 `lessons` 里总结方法，不保留散落脚本。
- 已经失去价值的临时脚本，统一视为 deprecated 候选，不再当作主流程资产。

## 12. 当前 `tmp_*` 文件分类建议

### 保留 / 已迁移价值
- `backend/tests/test_layout_audits.py`
  - 已把 `tmp_overlap_audit.py`、`tmp_overlap_latest_pptx.py`、`tmp_text_overflow_audit.py`、`tmp_text_overflow_audit2.py` 的核心逻辑正式化。
- `backend/tests/test_fidelity_score.py`
  - 已吸收 `tmp_fidelity_score.py` 的主价值：真实链路 fidelity 回归。
- `backend/tests/test_real_pipeline.py`
  - 已吸收 `tmp_regen_from_cache.py` 的主价值：缓存回放 + 真实 PPTX 验证。
- `lessons/openclaw_fidelity_lessons.md`
  - 已吸收 `tmp_compare_output_folders.py`、`tmp_compare_slide4_xml.py`、`tmp_find_threshold_ai_bug.py`、`tmp_parser_codepoints_slide4.py`、`tmp_ai_exact_repro.py`、`tmp_ai_prefix_repro.py` 的定位结论。

### 适合保留为临时工具，但不进主流程
- `backend/tmp_regen_from_cache.py`
  - 还能用于手工复跑缓存，但正式回归已进入测试。
- `backend/tmp_fidelity_score.py`
  - 还能用于手工打印分项分数，但测试已替代其核心价值。
- `backend/tmp_overlap_audit.py`
  - 还能用于临时排查 overlap，但正式版本已落地测试。
- `backend/tmp_text_overflow_audit.py`
  - 还能用于临时排查 overflow，但正式版本已落地测试。

### 建议降级为 deprecated / 后续删除
- `backend/tmp_ai_roundtrip.py`
  - 仅用于验证一个最小生成链路，不再承担独立价值。
- `backend/tmp_inspect_*`
  - 大部分是一次性观察脚本，除非后续再次复现同类问题，否则建议批量归档或删除。
- `backend/tmp_debug_*`
  - 诊断粒度强，但复用率低；若没有明确复用场景，建议删除。
- `backend/tmp_latest_pptx.py`
- `backend/tmp_list_openclaw_pptx.py`
- `backend/tmp_find_current_openclaw.py`
  - 这些多为辅助定位最新产物路径的脚本，价值可由标准日志或测试输出替代。

### 建议直接清理的候选
- `backend/tmp_codepoints.py`
- `backend/tmp_mutation_check.py`
- `backend/tmp_text_stats.py`
- `backend/tmp_diag_action_v4.py`
  - 这类脚本通常只服务单次排障，若没有明确复现需求，优先清理。

## 13. 从 `diag_*` 摘要里还能复用什么
- `diag_*` JSON 不只是调试快照，也能沉淀为**渲染策略证据**。
- 例如 `diag_palantir_summary.json` 里，`roadmap_overview`、`infographic_node_map` 等页的 `default_render_mode` / `current_render_mode` / `confidence` 字段，可以反向验证当前页级策略是否稳定。
- 可复用的判断方式：
  - `archetype` 置信度高，但 `render_mode` 置信度低时，优先怀疑渲染模式分类而不是结构识别。
  - `text_count` 很高、`image_count` 很低的页，不要因为名字像 infographic 就盲目切到激进图片策略。
  - `default_render_mode` 与 `current_render_mode` 长期一致时，可以把该页型视为稳定样本，用于回归基线。
- 以后如果继续产出 `diag_*`，优先抽取：
  - 页型分布
  - `render_mode` 命中率
  - 低置信度页面
  - 与最终 fidelity 低页的交集

## 14. `diag_action_system_summary*` 的可复用结论
- 这组 `diag_action_system_summary.json` / `v2` / `v3` / `v4` 主要价值不是单次排障，而是**稳定的页型基线**。
- 这套 16 页里，主要分布是：
  - `single_visual_explainer`
  - 大量 `infographic_node_map`
  - 少量 `two_column_compare`
  - 末尾 `multi_visual_explainer`
- 共同特征：
  - `archetype` 置信度几乎固定在 `0.8`
  - `render_mode` 置信度多为 `0.55`，只有 `image_fallback` 时到 `0.65`
  - `default_render_mode` 与 `current_render_mode` 在四个版本里高度一致，说明这些页是稳定回归样本
- 可直接提炼的规则：
  - **不要只看 archetype 名字**，要联动 `element_count`、`text_count`、`image_count`。
  - **文本多不等于必须 image_fallback**：例如部分 `infographic_node_map` 页 `text_count` 高、`image_count` 低，仍然适合 `auto`。
  - **roadmap_overview / 高密度信息页** 可以是 `image_fallback`，但这类决策应由结构密度和视觉负担共同决定，不应由单一标签决定。
  - **可把这组摘要当作未来 heuristic 改动的回归基线**：新规则不应让稳定页型的 `render_mode` 大面积漂移。
- 后续如果继续产出同类摘要，建议额外记录：
  - 哪些页从 `auto` 变成 `image_fallback`
  - 哪些页的 `render_mode` 置信度从 `0.55` 升到 `0.65`
  - 哪些页最终 fidelity 下降，作为 heuristic 反例
