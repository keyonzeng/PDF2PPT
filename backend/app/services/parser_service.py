import json
from pathlib import Path
from typing import Dict, Any, Optional
from app.core.models import Presentation, Slide, TextElement, ImageElement, TableElement, Element, DocumentStyleProfile, StyleToken

def _infer_text_role(item: Dict[str, Any]) -> Optional[str]:
    text_level = item.get("text_level")
    text = (item.get("text") or "").strip()
    if not text:
        return None

    if text_level == 1:
        return "title"
    if text_level == 2:
        return "subtitle"
    return "body"


def _split_inline_parenthetical_text(content: str) -> Optional[list[str]]:
    normalized = (content or "").strip()
    if "（" not in normalized or "）" not in normalized:
        return None
    prefix, suffix = normalized.split("（", 1)
    prefix = prefix.strip()
    suffix = ("（" + suffix).strip()
    if not prefix or not suffix:
        return None
    if len(normalized) < 12:
        return None
    if not prefix[0].isdigit() and not prefix.startswith(("第", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十")):
        return None
    return [prefix, suffix]

def _resolve_artifact_paths(base_path: Path) -> tuple[Optional[Path], Optional[Path]]:
    middle_json_path: Optional[Path] = None
    content_list_path: Optional[Path] = None
    folder_name = base_path.name

    for path in base_path.rglob("*.json"):
        name = path.name
        if middle_json_path is None and name.endswith("_middle.json"):
            middle_json_path = path
        if content_list_path is None and name.endswith("_content_list.json"):
            content_list_path = path
        if middle_json_path and content_list_path:
            return middle_json_path, content_list_path

    if middle_json_path is None:
        for method in ["hybrid_auto", "auto", "linear_auto"]:
            candidate = base_path / method / f"{folder_name}_middle.json"
            if candidate.exists():
                middle_json_path = candidate
                break

    if content_list_path is None:
        for method in ["hybrid_auto", "auto", "linear_auto"]:
            candidate = base_path / method / f"{folder_name}_content_list.json"
            if candidate.exists():
                content_list_path = candidate
                break

    return middle_json_path, content_list_path

def _collapse_artificial_spaces(text: str) -> str:
    """Heuristic: collapse single-character-spaced OCR artifacts like 'T h e L a s t L e a f'."""
    if not text or len(text) < 6:
        return text
    # If the text looks like "X X X X" where almost every char is followed by a space
    stripped = text.replace(" ", "")
    space_count = text.count(" ")
    char_count = len(stripped)
    if char_count > 3 and space_count > char_count * 0.4:
        return stripped
    return text


def _extract_text_from_middle_block(block: Dict[str, Any]) -> str:
    parts = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            content = span.get("content")
            if content:
                parts.append(_collapse_artificial_spaces(str(content).strip()))
    return " ".join(part for part in parts if part).strip()


def _extract_line_texts_from_middle_block(block: Dict[str, Any]) -> list[str]:
    line_texts: list[str] = []
    for line in block.get("lines", []):
        parts: list[str] = []
        for span in line.get("spans", []):
            content = span.get("content")
            if content:
                parts.append(_collapse_artificial_spaces(str(content).strip()))
        line_text = " ".join(part for part in parts if part).strip()
        if line_text:
            line_texts.append(line_text)
    return line_texts


def _extract_line_bboxes_from_middle_block(block: Dict[str, Any]) -> list[list[float]]:
    line_bboxes: list[list[float]] = []
    for line in block.get("lines", []):
        bbox = line.get("bbox") or []
        if len(bbox) != 4:
            continue
        line_bboxes.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])])
    return line_bboxes


def _extract_text_style_from_middle_block(block: Dict[str, Any]) -> Dict[str, Any]:
    style: Dict[str, Any] = {}
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if not isinstance(span, dict):
                continue
            if not style.get("font_name"):
                for key in ("font_name", "font", "font_family", "fontfamily"):
                    value = span.get(key)
                    if value:
                        style["font_name"] = str(value)
                        break
            if not style.get("color"):
                for key in ("color", "font_color", "text_color"):
                    value = span.get(key)
                    if value:
                        style["color"] = str(value)
                        break
            if "bold" not in style:
                for key in ("bold", "is_bold"):
                    value = span.get(key)
                    if value is not None:
                        style["bold"] = bool(value)
                        break
        if style:
            break
    return style


def _infer_text_alignment(block: Dict[str, Any], page_width: float, page_height: float | None = None) -> str:
    bbox = block.get("bbox") or []
    if len(bbox) != 4 or not page_width:
        return "left"
    x0, _, x1, _ = [float(value) for value in bbox]
    left_margin = x0 / page_width
    right_margin = max(page_width - x1, 0.0) / page_width
    center_x = ((x0 + x1) / 2) / page_width
    width_ratio = max((x1 - x0) / page_width, 0.0)
    top_ratio = 0.0
    if page_height:
        top_ratio = float(bbox[1]) / page_height
    content = _extract_text_from_middle_block(block)
    content_length = len(content.strip())

    if content_length <= 8 and any(ch.isdigit() for ch in content):
        if right_margin < left_margin * 0.8:
            return "right"
        if left_margin < right_margin * 0.8:
            return "left"
        return "center"

    if top_ratio < 0.22 and width_ratio > 0.45 and content_length > 8:
        return "center"

    if top_ratio > 0.55 and width_ratio > 0.25 and content_length > 12:
        return "center"

    if abs(center_x - 0.5) <= 0.04 and abs(left_margin - right_margin) <= 0.04 and width_ratio <= 0.45:
        return "center"
    if left_margin > 0.45 and right_margin < 0.15:
        return "right"
    return "left"


def _font_size_hint(role: str | None, content: str | None = None) -> tuple[float, float]:
    content_length = len((content or "").strip())
    if role == "title":
        return 0.48, 34.0
    if role == "subtitle":
        if content_length <= 8 or ((content or "").strip().isdigit()):
            return 0.55, 20.0
        return 0.24, 24.0
    if role == "caption":
        return 0.20, 14.0
    return 0.28, 20.0


def _estimate_middle_font_size(block: Dict[str, Any], page_height: float, role: str | None = None) -> Optional[float]:
    if not page_height:
        return None
    line_heights: list[float] = []
    for line in block.get("lines", []):
        bbox = line.get("bbox") or []
        if len(bbox) != 4:
            continue
        line_heights.append(max(float(bbox[3]) - float(bbox[1]), 0.0))
    if not line_heights:
        bbox = block.get("bbox") or []
        if len(bbox) == 4:
            line_heights.append(max(float(bbox[3]) - float(bbox[1]), 0.0))
    if not line_heights:
        return None
    avg_line_height = sum(line_heights) / len(line_heights)
    slide_height_points = 540.0
    content = _extract_text_from_middle_block(block)
    scale, cap = _font_size_hint(role, content)
    return max(min((avg_line_height / page_height) * slide_height_points * scale, cap), 8.0)


def _estimate_line_font_sizes(line_bboxes: list[list[float]], page_height: float, role: str | None = None) -> list[float]:
    if not page_height:
        return []
    slide_height_points = 540.0
    scale, cap = _font_size_hint(role)
    font_sizes: list[float] = []
    for bbox in line_bboxes:
        if len(bbox) != 4:
            continue
        line_height = max(float(bbox[3]) - float(bbox[1]), 0.0)
        font_sizes.append(max(min((line_height / page_height) * slide_height_points * scale, cap), 8.0))
    return font_sizes

def _extract_image_path_from_middle_block(block: Dict[str, Any]) -> str:
    for nested_block in block.get("blocks", []):
        for line in nested_block.get("lines", []):
            for span in line.get("spans", []):
                image_path = span.get("image_path")
                if image_path:
                    return str(image_path)
    return ""

def _resolve_middle_image_path(output_base_path: Path, image_rel_path: str) -> Path:
    direct_path = (output_base_path / image_rel_path).resolve()
    if direct_path.exists():
        return direct_path

    images_path = (output_base_path / "images" / image_rel_path).resolve()
    if images_path.exists():
        return images_path

    return direct_path

def _infer_middle_text_role(block: Dict[str, Any], page_width: float, page_height: float, archetype: str) -> tuple[Optional[int], str]:
    block_type = (block.get("type") or "").lower()
    bbox = block.get("bbox") or []
    if block_type == "title":
        return 1, "title"
    if len(bbox) != 4:
        return None, "body"

    x0, y0, x1, y1 = [float(value) for value in bbox]
    width_ratio = max((x1 - x0) / page_width, 0.0) if page_width else 0.0
    height_ratio = max((y1 - y0) / page_height, 0.0) if page_height else 0.0
    top_ratio = y0 / page_height if page_height else 0.0

    content = _extract_text_from_middle_block(block)
    content_length = len(content.strip())

    if archetype == "cover_split" and top_ratio > 0.75 and content_length <= 40:
        return 2, "subtitle"
    if archetype == "closing_statement" and top_ratio > 0.6 and content_length <= 60:
        return 2, "subtitle"
    if archetype == "two_column_compare" and content.startswith("202"):
        if content_length <= 8:
            return None, "subtitle"
        return None, "body"
    if archetype == "roadmap_overview" and width_ratio < 0.12 and content_length <= 10:
        return None, "caption"
    if archetype == "infographic_node_map" and width_ratio < 0.15 and height_ratio < 0.12:
        return None, "caption"
    if top_ratio < 0.3 and width_ratio > 0.18 and content_length <= 36:
        return 2, "subtitle"
    return None, "body"

def _map_middle_block_to_element(block: Dict[str, Any], output_base_path: Path, page_idx: int, page_width: float, page_height: float, archetype: str) -> Optional[Element]:
    block_type = (block.get("type") or "").lower()
    bbox = block.get("bbox")

    if block_type in {"title", "text"}:
        line_texts = _extract_line_texts_from_middle_block(block)
        line_bboxes = _extract_line_bboxes_from_middle_block(block)
        style = _extract_text_style_from_middle_block(block)
        content = "\n".join(line_texts).strip() or _extract_text_from_middle_block(block)
        if not content:
            return None
        text_level, semantic_role = _infer_middle_text_role(block, page_width, page_height, archetype)
        content_stripped = content.strip()
        is_short_year_label = archetype == "two_column_compare" and semantic_role == "subtitle" and len(content_stripped) <= 8 and content_stripped.isdigit()
        return TextElement(
            content=content,
            bbox=bbox,
            page_id=page_idx,
            text_level=text_level,
            semantic_role=semantic_role,
            align=_infer_text_alignment(block, page_width, page_height),
            font_size=_estimate_middle_font_size(block, page_height, semantic_role),
            bold=style.get("bold") if style.get("bold") is not None else (block_type == "title" or is_short_year_label),
            color=style.get("color"),
            font_name=style.get("font_name"),
            line_texts=line_texts or None,
            line_bboxes=line_bboxes or None,
            line_font_sizes=(
                [max(float(font_size := _estimate_middle_font_size(block, page_height, semantic_role) or 0.0), 8.0), max((font_size or 0.0) * 0.62, 8.0)]
                if archetype == "infographic_node_map" and semantic_role == "title" and len(line_texts) == 2 and len(line_bboxes) == 2
                else _estimate_line_font_sizes(line_bboxes, page_height, semantic_role) or None
            ),
        )

    if block_type == "image":
        image_rel_path = _extract_image_path_from_middle_block(block)
        if not image_rel_path:
            return None
        full_img_path = _resolve_middle_image_path(output_base_path, image_rel_path)
        return ImageElement(
            content="[IMAGE]",
            path=str(full_img_path),
            bbox=bbox,
            page_id=page_idx,
        )

    return None

def _load_page_sizes(middle_json_path: Optional[Path]) -> Dict[int, tuple[float, float]]:
    if not middle_json_path or not middle_json_path.exists():
        return {}

    with open(middle_json_path, "r", encoding="utf-8") as f:
        middle_data = json.load(f)

    page_sizes: Dict[int, tuple[float, float]] = {}
    for page in middle_data.get("pdf_info", []):
        page_idx = page.get("page_idx")
        page_size = page.get("page_size") or []
        if page_idx is None or len(page_size) != 2:
            continue
        page_sizes[int(page_idx)] = (float(page_size[0]), float(page_size[1]))

    return page_sizes

def _is_ppt_like_page(blocks: list[Dict[str, Any]]) -> bool:
    title_count = sum(1 for block in blocks if (block.get("type") or "").lower() == "title")
    text_count = sum(1 for block in blocks if (block.get("type") or "").lower() == "text")
    image_count = sum(1 for block in blocks if (block.get("type") or "").lower() == "image")
    total_count = len(blocks)
    return (
        title_count >= 1 and image_count >= 1 and total_count <= 14
    ) or (
        title_count >= 1 and text_count <= 8 and total_count <= 10
    )


def _merge_text_elements(elements: list[Element], page_width: float, page_height: float) -> list[Element]:
    text_elements = [element for element in elements if isinstance(element, TextElement) and element.bbox and (element.content or "").strip()]
    other_elements = [element for element in elements if element not in text_elements]

    text_elements.sort(key=lambda element: (element.bbox[1], element.bbox[0]))
    merged: list[TextElement] = []

    for element in text_elements:
        if not merged:
            merged.append(element.model_copy(deep=True))
            continue

        previous = merged[-1]
        prev_bbox = previous.bbox or []
        curr_bbox = element.bbox or []
        if len(prev_bbox) != 4 or len(curr_bbox) != 4:
            merged.append(element.model_copy(deep=True))
            continue

        same_role = getattr(previous, "semantic_role", None) == getattr(element, "semantic_role", None)
        same_level = getattr(previous, "text_level", None) == getattr(element, "text_level", None)
        prev_width = max(prev_bbox[2] - prev_bbox[0], 1.0)
        curr_width = max(curr_bbox[2] - curr_bbox[0], 1.0)
        left_delta = abs(prev_bbox[0] - curr_bbox[0]) / max(page_width, 1.0)
        right_delta = abs(prev_bbox[2] - curr_bbox[2]) / max(page_width, 1.0)
        vertical_gap = (curr_bbox[1] - prev_bbox[3]) / max(page_height, 1.0)
        width_ratio = min(prev_width, curr_width) / max(prev_width, curr_width)

        can_merge = (
            same_role
            and same_level
            and getattr(previous, "semantic_role", None) in {"body", "subtitle", "caption"}
            and -0.01 <= vertical_gap <= 0.035
            and left_delta <= 0.03
            and right_delta <= 0.04
            and width_ratio >= 0.6
        )

        if not can_merge:
            merged.append(element.model_copy(deep=True))
            continue

        previous.content = f"{(previous.content or '').rstrip()} {(element.content or '').lstrip()}".strip()
        previous.bbox = [
            min(prev_bbox[0], curr_bbox[0]),
            min(prev_bbox[1], curr_bbox[1]),
            max(prev_bbox[2], curr_bbox[2]),
            max(prev_bbox[3], curr_bbox[3]),
        ]

    return [*other_elements, *merged]

def _classify_slide_archetype(blocks: list[Dict[str, Any]], page_idx: int) -> str:
    title_count = sum(1 for block in blocks if (block.get("type") or "").lower() == "title")
    text_count = sum(1 for block in blocks if (block.get("type") or "").lower() == "text")
    image_count = sum(1 for block in blocks if (block.get("type") or "").lower() == "image")
    list_count = sum(1 for block in blocks if (block.get("type") or "").lower() == "list")

    if page_idx == 0 and image_count == 1 and title_count >= 1:
        return "cover_split"
    if image_count == 1 and text_count >= 10:
        return "roadmap_overview"
    if list_count > 0 or title_count >= 5:
        return "infographic_node_map"
    if image_count >= 2 and text_count >= 3:
        return "two_column_compare"
    if image_count >= 2:
        return "multi_visual_explainer"
    if image_count == 0 and text_count >= 2:
        return "policy_text_heavy"
    if page_idx >= 28 and title_count >= 1 and text_count <= 2:
        return "closing_statement"
    return "single_visual_explainer"

def _build_style_profile(pages: list[Dict[str, Any]]) -> DocumentStyleProfile:
    if not pages:
        return DocumentStyleProfile()

    first_page_size = pages[0].get("page_size") or [1280.0, 720.0]
    if len(first_page_size) != 2:
        first_page_size = [1280.0, 720.0]

    page_width = float(first_page_size[0])
    page_height = float(first_page_size[1])

    title_left_ratios: list[float] = []
    title_top_ratios: list[float] = []
    content_left_ratios: list[float] = []
    content_top_ratios: list[float] = []
    content_right_ratios: list[float] = []
    content_bottom_ratios: list[float] = []
    font_name_candidates: list[str] = []

    for page in pages:
        blocks = page.get("para_blocks", [])
        for block in blocks:
            bbox = block.get("bbox") or []
            if len(bbox) != 4:
                continue

            x0, y0, x1, y1 = [float(value) for value in bbox]
            block_type = (block.get("type") or "").lower()
            style = _extract_text_style_from_middle_block(block)
            font_name = style.get("font_name")
            if font_name:
                font_name_candidates.append(str(font_name))
            if block_type == "title":
                title_left_ratios.append(x0 / page_width)
                title_top_ratios.append(y0 / page_height)
            else:
                content_left_ratios.append(x0 / page_width)
                content_top_ratios.append(y0 / page_height)
                content_right_ratios.append(x1 / page_width)
                content_bottom_ratios.append(y1 / page_height)

    def _avg(values: list[float], fallback: float) -> float:
        return sum(values) / len(values) if values else fallback

    default_font_name = next((font_name for font_name in font_name_candidates if font_name), None)

    return DocumentStyleProfile(
        page_width=page_width,
        page_height=page_height,
        title_left_ratio=_avg(title_left_ratios, 0.05),
        title_top_ratio=_avg(title_top_ratios, 0.08),
        content_left_ratio=_avg(content_left_ratios, 0.05),
        content_top_ratio=_avg(content_top_ratios, 0.18),
        content_right_ratio=_avg(content_right_ratios, 0.95),
        content_bottom_ratio=_avg(content_bottom_ratios, 0.92),
        primary_color="#203040",
        secondary_color="#787878",
        accent_color="#0F3A78",
        title_style=StyleToken(font_size=28.0, color="#203040", bold=True, align="left", font_name=default_font_name),
        subtitle_style=StyleToken(font_size=18.0, color="#787878", bold=False, align="left", font_name=default_font_name),
        body_style=StyleToken(font_size=16.0, color="#203040", bold=False, align="left", font_name=default_font_name),
        caption_style=StyleToken(font_size=12.0, color="#787878", bold=False, align="left", font_name=default_font_name),
    )

def parse_mineru_output(output_folder: str) -> Presentation:
    """
    Parses the output of Mineru for a specific output folder into a Presentation object.
    
    Args:
        output_folder: Folder where MinerU wrote the parsed assets for one PDF
    """
    base_path = Path(output_folder)
    middle_json_path, content_list_path = _resolve_artifact_paths(base_path)

    if (not middle_json_path or not middle_json_path.exists()) and (not content_list_path or not content_list_path.exists()):
        raise FileNotFoundError(f"Could not find MinerU artifacts in {base_path}")

    if middle_json_path and middle_json_path.exists():
        with open(middle_json_path, "r", encoding="utf-8") as f:
            middle_data = json.load(f)

        pages = middle_data.get("pdf_info", [])
        style_profile = _build_style_profile(pages)
        presentation = Presentation(style_profile=style_profile)
        output_base_path = middle_json_path.parent
        for page in pages:
            page_idx = int(page.get("page_idx", 0))
            page_size = page.get("page_size") or [1280.0, 720.0]
            page_blocks = page.get("para_blocks", [])
            archetype = _classify_slide_archetype(page_blocks, page_idx)
            if len(page_size) != 2:
                page_size = [1280.0, 720.0]
            page_width = float(page_size[0])
            page_height = float(page_size[1])
            slide = Slide(
                page_id=page_idx + 1,
                width=page_width,
                height=page_height,
                archetype=archetype,
                style_profile=style_profile,
            )
            for block in page_blocks:
                element = _map_middle_block_to_element(block, output_base_path, page_idx, page_width, page_height, archetype)
                if element:
                    slide.add_element(element)
            if _is_ppt_like_page(page_blocks):
                slide.elements = _merge_text_elements(slide.elements, page_width, page_height)
            presentation.slides.append(slide)

        if presentation.slides:
            presentation.metadata["style_source"] = "middle_json"
            return presentation

    if not content_list_path or not content_list_path.exists():
        raise FileNotFoundError(f"Could not find content_list.json fallback in {base_path}")

    # Load JSON
    with open(content_list_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    presentation = Presentation()
    page_sizes = _load_page_sizes(middle_json_path)
    current_slide = None
    current_page_idx = -1

    for item in data:
        page_idx = item.get("page_idx", 0)
        
        # Create new slide if page changed
        if page_idx != current_page_idx:
            slide_width, slide_height = page_sizes.get(page_idx, (1280.0, 720.0))
            current_slide = Slide(page_id=page_idx + 1, width=slide_width, height=slide_height) # 1-based for users
            presentation.slides.append(current_slide)
            current_page_idx = page_idx
        
        # Map item to Element
        element = _map_item_to_element(item, content_list_path.parent)
        if element and current_slide:
            current_slide.add_element(element)

    return presentation

def _map_item_to_element(item: Dict[str, Any], output_base_path: Path) -> Optional[Element]:
    type_str = item.get("type", "").lower()
    bbox = item.get("bbox") # [x0, y0, x1, y1] on 1000x1000 scale
     
    if type_str == "text":
        return TextElement(
            content=item.get("text", ""),
            bbox=bbox,
            page_id=item.get("page_idx", 0),
            text_level=item.get("text_level"),
            semantic_role=_infer_text_role(item),
        )
    elif type_str == "image":
        img_rel_path = item.get("img_path", "")
        # Resolve absolute path for frontend/processing
        # item img_path might be relative to the json file location
        full_img_path = (output_base_path / img_rel_path).resolve()
        return ImageElement(
            content="[IMAGE]",
            path=str(full_img_path),
            bbox=bbox,
            page_id=item.get("page_idx", 0)
        )
    elif type_str == "table":
            # Table might have 'html' or 'img_path'
        html = item.get("table_body", "") 
        # Fallback to img if html is empty
        if not html and item.get("img_path"):
                full_img_path = (output_base_path / item.get("img_path")).resolve()
                return ImageElement(
                    content="[TABLE IMAGE]", 
                    path=str(full_img_path), 
                    bbox=bbox, 
                    page_id=item.get("page_idx", 0),
                    type="image" # Force type to image if we fall back? Or keep as table? Model says TableElement has html. 
                                # If we return ImageElement it must be compatible. 
                                # The original code returned ImageElement in fallback.
                )
        
        return TableElement(
            content="[TABLE]",
            html=html,
            bbox=bbox,
            page_id=item.get("page_idx", 0)
        )
    elif type_str == "equation" or type_str == "interline_equation":
        # treat as text for now
        return TextElement(
            content=item.get("text", "") or "[EQUATION]",
            bbox=bbox,
            page_id=item.get("page_idx", 0),
            semantic_role="body",
        )
         
    return None
