import io

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.util import Pt, Inches
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from PIL import Image
from app.core.models import Presentation as DomainPresentation
from app.core.models import TextElement, DocumentStyleProfile
from pathlib import Path

try:
    import pypdfium2 as pdfium
except ImportError:  # pragma: no cover - optional runtime dependency
    pdfium = None

# Minimalist PPT Generator
BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = BASE_DIR / "assets" / "templates"
OUTPUT_DIR = BASE_DIR / "mineru_output"


def _hex_to_rgb(color: str | None, fallback: tuple[int, int, int]) -> RGBColor:
    if not color:
        return RGBColor(*fallback)
    normalized = color.lstrip("#")
    if len(normalized) != 6:
        return RGBColor(*fallback)
    try:
        return RGBColor(int(normalized[0:2], 16), int(normalized[2:4], 16), int(normalized[4:6], 16))
    except ValueError:
        return RGBColor(*fallback)


def _effective_style_profile(presentation: DomainPresentation) -> DocumentStyleProfile:
    if presentation.style_profile:
        return presentation.style_profile
    return DocumentStyleProfile()


def _build_base_presentation(presentation: DomainPresentation) -> Presentation:
    prs = Presentation()
    profile = _effective_style_profile(presentation)
    aspect_ratio = profile.page_width / profile.page_height if profile.page_height else (16 / 9)
    slide_height_inches = 7.5
    slide_width_inches = slide_height_inches * aspect_ratio
    prs.slide_width = Inches(slide_width_inches)
    prs.slide_height = Inches(slide_height_inches)
    return prs


def _remove_existing_slides(prs: Presentation) -> None:
    slide_id_list = prs.slides._sldIdLst
    for slide_id in list(slide_id_list):
        rel_id = slide_id.rId
        prs.part.drop_rel(rel_id)
        slide_id_list.remove(slide_id)


def _blank_layout(prs: Presentation):
    return min(prs.slide_layouts, key=lambda layout: len(layout.placeholders))


def _remove_slide_placeholders(slide) -> None:
    for shape in list(slide.shapes):
        if not shape.is_placeholder:
            continue
        element = shape.element
        element.getparent().remove(element)


def _is_cover_slide(d_slide) -> bool:
    if getattr(d_slide, "archetype", None) == "cover_split":
        return True
    text_elements = [element for element in d_slide.elements if element.type == "text" and getattr(element, "content", "").strip()]
    image_elements = [element for element in d_slide.elements if element.type in {"image", "table"}]
    return d_slide.page_id == 1 and len(text_elements) <= 3 and len(image_elements) == 1


def _alignment_value(value: str | None):
    if value == "center":
        return PP_ALIGN.CENTER
    if value == "right":
        return PP_ALIGN.RIGHT
    return PP_ALIGN.LEFT


def _set_run_font_name(run, font_name: str) -> None:
    if not font_name:
        return
    run.font.name = font_name
    r_pr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        font = r_pr.find(qn(tag))
        if font is None:
            font = OxmlElement(tag)
            r_pr.append(font)
        font.set("typeface", font_name)


def _apply_run_inline_styles(run, elem: TextElement) -> None:
    italic = getattr(elem, "italic", None)
    underline = getattr(elem, "underline", None)
    strikethrough = getattr(elem, "strikethrough", None)

    if italic is not None:
        run.font.italic = bool(italic)
    if underline is not None:
        run.font.underline = bool(underline)
    if strikethrough is not None:
        r_pr = run._r.get_or_add_rPr()
        if bool(strikethrough):
            r_pr.set("strike", "sngStrike")
        else:
            r_pr.attrib.pop("strike", None)


def _infer_font_name(text: str, preferred: str | None = None) -> str:
    if preferred:
        return preferred
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return "Microsoft YaHei"
    return "Arial"


def _normalized_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _box_height_points(textbox) -> float:
    return textbox.height / 12700 if textbox.height else 0.0


def _resolved_font_size_pt(textbox, elem: TextElement, fallback: float) -> float:
    explicit = getattr(elem, "font_size", None)
    if explicit:
        return max(float(explicit), 8.0)
    line_count = max(len(getattr(elem, "line_texts", None) or [line for line in (elem.content or "").splitlines() if line.strip()]), 1)
    box_height = _box_height_points(textbox)
    if box_height <= 0:
        return fallback
    estimated = box_height * 0.72 if line_count == 1 else box_height / (line_count * 1.35)
    return max(min(estimated, box_height * 0.85 if box_height else estimated), 8.0)


def _paragraph_font_size_pt(textbox, elem: TextElement, paragraph_index: int, fallback: float) -> float:
    line_font_sizes = getattr(elem, "line_font_sizes", None) or []
    if paragraph_index < len(line_font_sizes):
        return max(float(line_font_sizes[paragraph_index]), 8.0)
    return _resolved_font_size_pt(textbox, elem, fallback)


def _should_word_wrap_text(elem: TextElement, content: str, line_texts: list[str]) -> bool:
    role = getattr(elem, "semantic_role", None)
    if role in {"body", "subtitle", "caption"} and len(content) >= 18:
        return True
    return False


def _apply_text_style(textbox, elem: TextElement, is_cover_slide: bool) -> None:
    text_frame = textbox.text_frame
    role = getattr(elem, "semantic_role", None)
    content = (elem.content or "").strip()
    slide = textbox.part.slide
    profile = getattr(slide, "_pdf2ppt_style_profile", None)
    archetype = getattr(slide, "_pdf2ppt_archetype", "single_visual_explainer")
    profile_font_name = getattr(getattr(profile, "body_style", None), "font_name", None)
    resolved_font_name = _infer_font_name(content, getattr(elem, "font_name", None) or profile_font_name)
    is_short_year_label = archetype == "two_column_compare" and role == "subtitle" and content.isdigit() and len(content) <= 8

    title_color = _hex_to_rgb(getattr(elem, "color", None), (17, 17, 17))
    subtitle_color = _hex_to_rgb(getattr(elem, "color", None), (48, 114, 208) if is_short_year_label else (68, 68, 68))
    accent_color = _hex_to_rgb(getattr(elem, "color", None), (17, 17, 17))

    for paragraph_index, paragraph in enumerate(text_frame.paragraphs):
        run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
        paragraph.alignment = _alignment_value(getattr(elem, "align", None) or getattr(getattr(profile, "body_style", None), "align", "left"))
        paragraph.space_before = Pt(0)
        paragraph.space_after = Pt(0)

        if is_cover_slide and role == "title":
            run.font.size = Pt(_paragraph_font_size_pt(textbox, elem, paragraph_index, 30) * 0.9)
            is_split_parenthetical_line = (paragraph_index > 0 and (paragraph.text or "").strip().startswith(("（", "("))) or content.startswith(("（", "("))
            run.font.bold = False if is_split_parenthetical_line else True
            run.font.color.rgb = subtitle_color if is_split_parenthetical_line else accent_color
            _set_run_font_name(run, _infer_font_name(content, getattr(elem, "font_name", None) or getattr(getattr(profile, "title_style", None), "font_name", None) or resolved_font_name))
            _apply_run_inline_styles(run, elem)
            paragraph.alignment = _alignment_value(getattr(elem, "align", None) or "left")
        elif is_cover_slide and role in {"subtitle", "body"} and len(content) <= 40:
            run.font.size = Pt(_paragraph_font_size_pt(textbox, elem, paragraph_index, 18) * 0.9)
            run.font.bold = bool(getattr(elem, "bold", None))
            run.font.color.rgb = subtitle_color
            _set_run_font_name(run, _infer_font_name(content, getattr(elem, "font_name", None) or getattr(getattr(profile, "subtitle_style", None), "font_name", None) or resolved_font_name))
            _apply_run_inline_styles(run, elem)
            paragraph.alignment = _alignment_value(getattr(elem, "align", None) or "left")
        elif role == "title":
            run.font.size = Pt(_paragraph_font_size_pt(textbox, elem, paragraph_index, getattr(getattr(profile, "title_style", None), "font_size", 24) or 24))
            is_split_parenthetical_line = (paragraph_index > 0 and (paragraph.text or "").strip().startswith(("（", "("))) or content.startswith(("（", "("))
            run.font.bold = False if is_split_parenthetical_line else (True if getattr(elem, "bold", None) is None else bool(getattr(elem, "bold", None)))
            run.font.color.rgb = subtitle_color if is_split_parenthetical_line else title_color
            _set_run_font_name(run, _infer_font_name(content, getattr(elem, "font_name", None) or getattr(getattr(profile, "title_style", None), "font_name", None) or resolved_font_name))
            _apply_run_inline_styles(run, elem)
            paragraph.alignment = _alignment_value(getattr(elem, "align", None) or getattr(getattr(profile, "title_style", None), "align", "left"))
        elif role == "subtitle":
            run.font.size = Pt(_paragraph_font_size_pt(textbox, elem, paragraph_index, getattr(getattr(profile, "subtitle_style", None), "font_size", 18) or 18))
            run.font.bold = bool(getattr(elem, "bold", None))
            run.font.color.rgb = subtitle_color
            _set_run_font_name(run, _infer_font_name(content, getattr(elem, "font_name", None) or getattr(getattr(profile, "subtitle_style", None), "font_name", None) or resolved_font_name))
            _apply_run_inline_styles(run, elem)
            paragraph.alignment = _alignment_value(getattr(elem, "align", None) or getattr(getattr(profile, "subtitle_style", None), "align", "left"))
        elif role == "caption":
            run.font.size = Pt(_paragraph_font_size_pt(textbox, elem, paragraph_index, getattr(getattr(profile, "caption_style", None), "font_size", 12) or 12))
            run.font.bold = bool(getattr(elem, "bold", None))
            run.font.color.rgb = subtitle_color
            _set_run_font_name(run, _infer_font_name(content, getattr(elem, "font_name", None) or getattr(getattr(profile, "caption_style", None), "font_name", None) or resolved_font_name))
            _apply_run_inline_styles(run, elem)
            paragraph.alignment = _alignment_value(getattr(elem, "align", None) or getattr(getattr(profile, "caption_style", None), "align", "left"))
        else:
            run.font.size = Pt(_paragraph_font_size_pt(textbox, elem, paragraph_index, getattr(getattr(profile, "body_style", None), "font_size", 16) or 16))
            run.font.bold = bool(getattr(elem, "bold", None))
            run.font.color.rgb = title_color
            _set_run_font_name(run, resolved_font_name)
            _apply_run_inline_styles(run, elem)

        if archetype == "single_visual_explainer" and role == "title" and run.font.size is not None:
            run.font.size = Pt(max(float(run.font.size.pt) * 0.92, 10.0))
        if archetype == "single_visual_explainer" and role in {"subtitle", "body", "caption"} and run.font.size is not None:
            run.font.size = Pt(max(float(run.font.size.pt) * 0.93, 8.0))

        if archetype == "infographic_node_map" and role == "caption":
            run.font.size = Pt(11)
            paragraph.alignment = PP_ALIGN.CENTER
        if archetype == "infographic_node_map" and role in {"subtitle", "body", "caption"} and run.font.size is not None:
            run.font.size = Pt(max(float(run.font.size.pt) * 0.85, 8.0))
        if archetype == "policy_text_heavy" and role == "title":
            run.font.size = Pt(26)

        if len(text_frame.paragraphs) > 1:
            if role == "title":
                paragraph.space_after = Pt(max(float(run.font.size.pt) * 0.22, 2.0))
            elif role in {"subtitle", "body", "caption"}:
                paragraph.space_after = Pt(max(float(run.font.size.pt) * 0.10, 1.0))

        font_size = run.font.size
        if font_size is not None:
            paragraph.line_spacing = Pt(max(float(font_size.pt) * 1.15, 1.0))


def _apply_archetype_layout_hints(slide, d_slide, profile: DocumentStyleProfile) -> None:
    slide._pdf2ppt_style_profile = profile
    slide._pdf2ppt_archetype = getattr(d_slide, "archetype", "single_visual_explainer")


def _sorted_elements_for_render(d_slide):
    def _rank(element):
        bbox = element.bbox or [0, 0, 0, 0]
        order = 0 if element.type in {"image", "table"} else 1
        return (order, bbox[1], bbox[0])

    return sorted(d_slide.elements, key=_rank)


def _element_geometry(elem, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = elem.bbox
    w = x1 - x0
    h = y1 - y0
    safe_pdf_w = max(float(pdf_w), 1.0)
    safe_pdf_h = max(float(pdf_h), 1.0)
    safe_ppt_w = max(int(ppt_w), 1)
    safe_ppt_h = max(int(ppt_h), 1)

    scale = min(safe_ppt_w / safe_pdf_w, safe_ppt_h / safe_pdf_h)
    scaled_page_w = safe_pdf_w * scale
    scaled_page_h = safe_pdf_h * scale
    offset_x = max((safe_ppt_w - scaled_page_w) / 2.0, 0.0)
    offset_y = max((safe_ppt_h - scaled_page_h) / 2.0, 0.0)

    left = int(round(offset_x + (x0 * scale)))
    top = int(round(offset_y + (y0 * scale)))
    width = max(int(round(w * scale)), 1)
    height = max(int(round(h * scale)), 1)
    return left, top, width, height


def _slide_page_index(d_slide) -> int:
    page_id = int(getattr(d_slide, "page_id", 1) or 1)
    return max(page_id - 1, 0)


def _render_text_element(slide, elem, left: int, top: int, width: int, height: int, is_cover_slide: bool) -> None:
    textbox = slide.shapes.add_textbox(left, top, width, height)
    textbox.fill.background()
    textbox.line.fill.background()
    tf = textbox.text_frame
    role = getattr(elem, "semantic_role", None)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    archetype = getattr(slide, "_pdf2ppt_archetype", "single_visual_explainer")
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE if role in {"body", "caption"} or (archetype == "infographic_node_map" and role == "subtitle") else MSO_AUTO_SIZE.NONE
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    line_texts = [line for line in (getattr(elem, "line_texts", None) or []) if line.strip()]
    content_text = (elem.content or "").replace("\n", "\v")
    normalized_content = _normalized_text(content_text.replace("\v", "\n"))
    normalized_line_texts = _normalized_text("\n".join(line_texts)) if line_texts else ""
    should_render_lines_as_paragraphs = len(line_texts) > 1 and normalized_line_texts == normalized_content and role in {"title", "subtitle"}
    if should_render_lines_as_paragraphs:
        first_paragraph = tf.paragraphs[0]
        first_paragraph.text = line_texts[0]
        for line_text in line_texts[1:]:
            paragraph = tf.add_paragraph()
            paragraph.text = line_text
    else:
        tf.text = content_text
    tf.word_wrap = _should_word_wrap_text(elem, elem.content or "", line_texts)
    _apply_text_style(textbox, elem, is_cover_slide)


def _iter_text_overlay_units(elem: TextElement, archetype: str | None = None) -> list[TextElement]:
    return [elem]


def _render_text_elements_only(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    archetype = getattr(d_slide, "archetype", None)
    for elem in _sorted_elements_for_render(d_slide):
        if elem.type != "text" or not elem.bbox:
            continue
        for overlay_elem in _iter_text_overlay_units(elem, archetype):
            if not overlay_elem.bbox:
                continue
            left, top, width, height = _element_geometry(overlay_elem, pdf_w, pdf_h, ppt_w, ppt_h)
            _render_text_element(slide, overlay_elem, left, top, width, height, is_cover_slide)


def _render_page_image(source_pdf_document, page_index: int, page_image_cache: dict[int, Image.Image]) -> Image.Image | None:
    cached = page_image_cache.get(page_index)
    if cached is not None:
        return cached

    if source_pdf_document is None or pdfium is None:
        return None

    try:
        page = source_pdf_document[page_index]
        bitmap = page.render(scale=8.0)
        pil_image = bitmap.to_pil()
    except Exception:
        return None

    page_image_cache[page_index] = pil_image
    return pil_image


def _render_picture_element(slide, elem, left: int, top: int, width: int, height: int, image_size_cache: dict[str, tuple[int, int]], source_pdf_document=None, page_index: int | None = None, pdf_w: float | None = None, pdf_h: float | None = None, page_image_cache: dict[int, Image.Image] | None = None) -> None:
    img_path = getattr(elem, "path", None)
    if img_path and Path(img_path).exists():
        _add_picture_cover(slide, img_path, left, top, width, height, image_size_cache)
        return

    if source_pdf_document is None or page_index is None or pdf_w is None or pdf_h is None:
        return

    if page_image_cache is None:
        page_image_cache = {}
    page_image = _render_page_image(source_pdf_document, page_index, page_image_cache)
    if page_image is None:
        return

    bbox = getattr(elem, "bbox", None) or []
    if len(bbox) != 4:
        return

    page_width, page_height = page_image.size
    x0, y0, x1, y1 = [float(value) for value in bbox]
    crop_left = max(0, min(page_width, int(round((x0 / max(pdf_w, 1.0)) * page_width))))
    crop_top = max(0, min(page_height, int(round((y0 / max(pdf_h, 1.0)) * page_height))))
    crop_right = max(crop_left + 1, min(page_width, int(round((x1 / max(pdf_w, 1.0)) * page_width))))
    crop_bottom = max(crop_top + 1, min(page_height, int(round((y1 / max(pdf_h, 1.0)) * page_height))))

    try:
        cropped = page_image.crop((crop_left, crop_top, crop_right, crop_bottom))
    except Exception:
        return

    stream = io.BytesIO()
    cropped.save(stream, format="PNG")
    stream.seek(0)
    slide.shapes.add_picture(stream, left, top, width=width, height=height)


def _page_snapshot_candidate(d_slide):
    visual_elements = [element for element in d_slide.elements if element.type in {"image", "table"} and getattr(element, "path", None)]
    if not visual_elements:
        return None

    def _area(element):
        bbox = element.bbox or [0, 0, 0, 0]
        if len(bbox) != 4:
            return 0
        return max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 0)

    return max(visual_elements, key=_area)


def _slide_has_visual_blocks(d_slide) -> bool:
    return any(element.type in {"image", "table"} for element in d_slide.elements)


def _has_resolvable_visual_assets(d_slide) -> bool:
    for element in d_slide.elements:
        if element.type not in {"image", "table"}:
            continue
        img_path = getattr(element, "path", None)
        if img_path and Path(img_path).exists():
            return True
    return False


def _snapshot_area_ratio(d_slide) -> float:
    snapshot = _page_snapshot_candidate(d_slide)
    if snapshot is None or not snapshot.bbox or len(snapshot.bbox) != 4:
        return 0.0
    page_area = max((d_slide.width or 1280.0) * (d_slide.height or 720.0), 1.0)
    bbox = snapshot.bbox
    snapshot_area = max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 0.0)
    return snapshot_area / page_area


def _render_page_snapshot(slide, d_slide, ppt_w: int, ppt_h: int, is_cover_slide: bool, image_size_cache: dict[str, tuple[int, int]]) -> bool:
    snapshot = _page_snapshot_candidate(d_slide)
    if snapshot is None:
        return False

    img_path = getattr(snapshot, "path", None)
    if not img_path or not Path(img_path).exists():
        return False

    _add_picture_cover(slide, img_path, 0, 0, ppt_w, ppt_h, image_size_cache)

    title_elements = [
        element
        for element in _sorted_elements_for_render(d_slide)
        if element.type == "text" and getattr(element, "semantic_role", None) in {"title", "subtitle"}
    ]

    for element in title_elements[:2]:
        if not element.bbox:
            continue
        left, top, width, height = _element_geometry(element, d_slide.width or 1280.0, d_slide.height or 720.0, ppt_w, ppt_h)
        _render_text_element(slide, element, left, top, width, height, is_cover_slide)

    return True


def _render_pdf_page_snapshot(slide, source_pdf_document, page_index: int, ppt_w: int, ppt_h: int) -> bool:
    if source_pdf_document is None or pdfium is None:
        return False

    try:
        page = source_pdf_document[page_index]
        bitmap = page.render(scale=8.0)
        pil_image = bitmap.to_pil()
    except Exception:
        return False

    stream = io.BytesIO()
    pil_image.save(stream, format="PNG")
    stream.seek(0)
    slide.shapes.add_picture(stream, 0, 0, width=ppt_w, height=ppt_h)
    return True


def _is_ppt_like_slide(d_slide, render_mode: str, source_pdf_document) -> bool:
    return False


def _render_title_overlays_only(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    title_elements = [
        element
        for element in _sorted_elements_for_render(d_slide)
        if element.type == "text" and getattr(element, "semantic_role", None) in {"title", "subtitle"}
    ]
    for element in title_elements[:3]:
        for overlay_elem in _iter_text_overlay_units(element):
            if not overlay_elem.bbox:
                continue
            left, top, width, height = _element_geometry(overlay_elem, pdf_w, pdf_h, ppt_w, ppt_h)
            _render_text_element(slide, overlay_elem, left, top, width, height, is_cover_slide)


def _render_ppt_like_fidelity(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool, image_size_cache: dict[str, tuple[int, int]], source_pdf_document=None) -> bool:
    render_mode = getattr(d_slide, "render_mode", "auto")
    if not _is_ppt_like_slide(d_slide, render_mode, source_pdf_document):
        return False
    if not _render_page_snapshot(slide, d_slide, ppt_w, ppt_h, is_cover_slide, image_size_cache):
        return False
    _render_text_elements_only(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)
    return True


def _render_generic_archetype(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool, image_size_cache: dict[str, tuple[int, int]], source_pdf_document=None) -> None:
    page_index = _slide_page_index(d_slide)
    page_image_cache: dict[int, Image.Image] = {}
    for elem in _sorted_elements_for_render(d_slide):
        if not elem.bbox:
            continue
        if elem.type == "text":
            for overlay_elem in _iter_text_overlay_units(elem):
                if not overlay_elem.bbox:
                    continue
                left, top, width, height = _element_geometry(overlay_elem, pdf_w, pdf_h, ppt_w, ppt_h)
                _render_text_element(slide, overlay_elem, left, top, width, height, is_cover_slide)
        elif elem.type in {"image", "table"}:
            left, top, width, height = _element_geometry(elem, pdf_w, pdf_h, ppt_w, ppt_h)
            _render_picture_element(
                slide,
                elem,
                left,
                top,
                width,
                height,
                image_size_cache,
                None if source_pdf_document is None else source_pdf_document,
                page_index,
                pdf_w,
                pdf_h,
                page_image_cache,
            )


def _render_cover_split(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, image_size_cache: dict[str, tuple[int, int]]) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, True, image_size_cache, None)


def _render_roadmap_overview(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool, image_size_cache: dict[str, tuple[int, int]]) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide, image_size_cache, None)


def _render_two_column_compare(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool, image_size_cache: dict[str, tuple[int, int]]) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide, image_size_cache, None)


def _render_policy_text_heavy(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool, image_size_cache: dict[str, tuple[int, int]]) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide, image_size_cache, None)


def _render_closing_statement(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool, image_size_cache: dict[str, tuple[int, int]]) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide, image_size_cache, None)


def _render_slide_by_archetype(
    slide,
    d_slide,
    pdf_w: float,
    pdf_h: float,
    ppt_w: int,
    ppt_h: int,
    is_cover_slide: bool,
    render_mode: str,
    image_size_cache: dict[str, tuple[int, int]],
    source_pdf_document=None,
) -> None:
    page_index = _slide_page_index(d_slide)
    text_elements = [element for element in d_slide.elements if element.type == "text" and getattr(element, "content", "").strip()]
    visual_elements = [element for element in d_slide.elements if element.type in {"image", "table"}]

    if render_mode in {"image_fallback", "hybrid_overlay"} and source_pdf_document is not None:
        if _render_pdf_page_snapshot(slide, source_pdf_document, page_index, ppt_w, ppt_h):
            return

    if render_mode == "editable":
        _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide, image_size_cache, source_pdf_document)
        return

    if _render_ppt_like_fidelity(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide, image_size_cache):
        return

    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide, image_size_cache, source_pdf_document)


def _get_image_size(img_path: str, image_size_cache: dict[str, tuple[int, int]]) -> tuple[int, int]:
    cached = image_size_cache.get(img_path)
    if cached:
        return cached

    with Image.open(img_path) as image:
        size = image.size

    image_size_cache[img_path] = size
    return size


def _add_picture_cover(slide, img_path: str, left: int, top: int, width: int, height: int, image_size_cache: dict[str, tuple[int, int]]) -> None:
    image_width, image_height = _get_image_size(img_path, image_size_cache)

    if image_width <= 0 or image_height <= 0:
        slide.shapes.add_picture(img_path, left, top, width=width, height=height)
        return

    picture = slide.shapes.add_picture(img_path, left, top, width=width, height=height)
    frame_aspect = width / height if height else 1
    image_aspect = image_width / image_height if image_height else frame_aspect

    if image_aspect > frame_aspect:
        crop = (1 - (frame_aspect / image_aspect)) / 2
        picture.crop_left = crop
        picture.crop_right = crop
        picture.crop_top = 0
        picture.crop_bottom = 0
    else:
        crop = (1 - (image_aspect / frame_aspect)) / 2 if frame_aspect else 0
        picture.crop_top = crop
        picture.crop_bottom = crop
        picture.crop_left = 0
        picture.crop_right = 0


def generate_pptx(
    presentation: DomainPresentation,
    template_key: str = "default",
    request_id: str | None = None,
    render_mode_overrides: dict[int, str] | None = None,
    source_pdf_path: str | None = None,
) -> str:
    """
    Convert Domain Presentation to PPTX file.
    Returns path to the generated file.
    """
    overrides = render_mode_overrides or {}
    image_size_cache: dict[str, tuple[int, int]] = {}
    source_pdf_document = None
    if source_pdf_path and pdfium is not None:
        source_path = Path(source_pdf_path)
        if source_path.exists():
            source_pdf_document = pdfium.PdfDocument(str(source_path))

    prs = _build_base_presentation(presentation)
    profile = _effective_style_profile(presentation)

    # Layout mapping (Naive)
    title_layout = _blank_layout(prs)
    content_layout = _blank_layout(prs)  # Title and Content

    # Iterate domain slides
    for i, d_slide in enumerate(presentation.slides):
        # Create PPT slide
        # If it's the first page, use Title layout? Or just content for all?
        # Let's use Content layout for now.
        layout = content_layout if i > 0 else title_layout
        slide = prs.slides.add_slide(layout)
        _remove_slide_placeholders(slide)
        is_cover_slide = _is_cover_slide(d_slide)
        _apply_archetype_layout_hints(slide, d_slide, profile)

        # Mapping Elements
        # Mineru elements: Text, Image, Table

        # Title handling: Mineru might have extracted a Title element.
        # But we don't have explicit "Title" type in Element yet.
        # We rely on TextElement content or just generic placement.

        # For structure-preserving, we might want to use Blank layout and place elements
        # at exact coordinates.
        # But Mineru bbox is [x0, y0, x1, y1] typically in PDF points (72dpi?).
        # PPTX uses Inches/EMUs.
        # Scale Factor: PDF Width / PPT Width

        # Use the actual template slide size instead of a hardcoded assumption.
        ppt_w = prs.slide_width
        ppt_h = prs.slide_height

        # Determine PDF scale
        # Domain Slide has width/height?
        pdf_w = d_slide.width if d_slide.width else 595.0  # A4 point width approx
        pdf_h = d_slide.height if d_slide.height else 842.0

        # We'll use a safer approach: Place elements relative to slide size using %
        # bbox is usually [x0, y0, x1, y1]

        render_mode = overrides.get(d_slide.page_id) or getattr(d_slide, "render_mode", None) or "auto"
        _render_slide_by_archetype(
            slide,
            d_slide,
            pdf_w,
            pdf_h,
            ppt_w,
            ppt_h,
            is_cover_slide,
            render_mode,
            image_size_cache,
            source_pdf_document,
        )

    # Save output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_filename = f"{request_id or 'generated'}_presentation.pptx"
    output_path = OUTPUT_DIR / output_filename
    prs.save(str(output_path))

    
    return str(output_path)
