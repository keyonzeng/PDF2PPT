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

def _find_first(base_path: Path, pattern: str) -> Optional[Path]:
    for path in base_path.rglob(pattern):
        return path
    return None

def _extract_text_from_middle_block(block: Dict[str, Any]) -> str:
    parts = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            content = span.get("content")
            if content:
                parts.append(str(content).strip())
    return " ".join(part for part in parts if part).strip()

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
        return 2, "subtitle"
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
        content = _extract_text_from_middle_block(block)
        if not content:
            return None
        text_level, semantic_role = _infer_middle_text_role(block, page_width, page_height, archetype)
        return TextElement(
            content=content,
            bbox=bbox,
            page_id=page_idx,
            text_level=text_level,
            semantic_role=semantic_role,
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

def _load_page_sizes(base_path: Path, folder_name: str) -> Dict[int, tuple[float, float]]:
    middle_json_path = None
    for path in base_path.rglob("*_middle.json"):
        middle_json_path = path
        break

    if not middle_json_path:
        candidate = base_path / "hybrid_auto" / f"{folder_name}_middle.json"
        if candidate.exists():
            middle_json_path = candidate

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

    for page in pages:
        blocks = page.get("para_blocks", [])
        for block in blocks:
            bbox = block.get("bbox") or []
            if len(bbox) != 4:
                continue

            x0, y0, x1, y1 = [float(value) for value in bbox]
            block_type = (block.get("type") or "").lower()
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
        title_style=StyleToken(font_size=28.0, color="#203040", bold=True, align="left"),
        subtitle_style=StyleToken(font_size=18.0, color="#787878", bold=False, align="left"),
        body_style=StyleToken(font_size=16.0, color="#203040", bold=False, align="left"),
        caption_style=StyleToken(font_size=12.0, color="#787878", bold=False, align="left"),
    )

def parse_mineru_output(output_folder: str) -> Presentation:
    """
    Parses the output of Mineru for a specific output folder into a Presentation object.
    
    Args:
        output_folder: Folder where MinerU wrote the parsed assets for one PDF
    """
    base_path = Path(output_folder)
    folder_name = base_path.name
    middle_json_path = _find_first(base_path, "*_middle.json")

    # Common paths
    # Mineru 2.x structure: output_dir / folder_name / parse_method (e.g. 'hybrid_auto') / folder_name_content_list.json
    # We need to find the correct subfolder.

    # Heuristic to find the valid output folder (linear_auto, hybrid_auto, etc.)
    # Usually it's the one containing .json files
    content_list_path = None

    # Search for content_list.json recursively
    for path in base_path.rglob("*_content_list.json"):
        content_list_path = path
        break

    if not content_list_path:
        # Fallback or error
        # Try finding via known methods
        potential_methods = ["hybrid_auto", "auto", "linear_auto"]
        for method in potential_methods:
            p = base_path / method / f"{folder_name}_content_list.json"
            if p.exists():
                content_list_path = p
                break

    if not content_list_path or not content_list_path.exists():
        raise FileNotFoundError(f"Could not find content_list.json in {base_path}")

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
            archetype = _classify_slide_archetype(page.get("para_blocks", []), page_idx)
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
            for block in page.get("para_blocks", []):
                element = _map_middle_block_to_element(block, output_base_path, page_idx, page_width, page_height, archetype)
                if element:
                    slide.add_element(element)
            presentation.slides.append(slide)

        if presentation.slides:
            presentation.metadata["style_source"] = "middle_json"
            return presentation

    # Load JSON
    with open(content_list_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    presentation = Presentation()
    page_sizes = _load_page_sizes(base_path, folder_name)
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
