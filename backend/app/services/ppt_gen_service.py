from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt, Inches
from PIL import Image
from app.core.models import Presentation as DomainPresentation
from app.core.models import TextElement, DocumentStyleProfile
from pathlib import Path

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


def _apply_text_style(textbox, elem: TextElement, is_cover_slide: bool) -> None:
    text_frame = textbox.text_frame
    paragraph = text_frame.paragraphs[0]
    run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
    role = getattr(elem, "semantic_role", None)
    content = (elem.content or "").strip()
    slide = textbox.part.slide
    profile = getattr(slide, "_pdf2ppt_style_profile", None)
    archetype = getattr(slide, "_pdf2ppt_archetype", "single_visual_explainer")

    title_color = _hex_to_rgb(getattr(profile, "primary_color", None), (32, 48, 64))
    subtitle_color = _hex_to_rgb(getattr(profile, "secondary_color", None), (120, 120, 120))
    accent_color = _hex_to_rgb(getattr(profile, "accent_color", None), (15, 58, 120))

    paragraph.alignment = _alignment_value(getattr(getattr(profile, "body_style", None), "align", "left"))

    if is_cover_slide and role == "title":
        run.font.size = Pt(36)
        run.font.bold = True
        run.font.color.rgb = accent_color
        paragraph.alignment = PP_ALIGN.LEFT
    elif is_cover_slide and role in {"subtitle", "body"} and len(content) <= 40:
        run.font.size = Pt(18)
        run.font.bold = False
        run.font.color.rgb = subtitle_color
        paragraph.alignment = PP_ALIGN.LEFT
    elif role == "title":
        run.font.size = Pt(getattr(getattr(profile, "title_style", None), "font_size", 24) or 24)
        run.font.bold = True
        run.font.color.rgb = title_color
        paragraph.alignment = _alignment_value(getattr(getattr(profile, "title_style", None), "align", "left"))
    elif role == "subtitle":
        run.font.size = Pt(getattr(getattr(profile, "subtitle_style", None), "font_size", 18) or 18)
        run.font.bold = False
        run.font.color.rgb = subtitle_color
        paragraph.alignment = _alignment_value(getattr(getattr(profile, "subtitle_style", None), "align", "left"))
    elif role == "caption":
        run.font.size = Pt(getattr(getattr(profile, "caption_style", None), "font_size", 12) or 12)
        run.font.bold = False
        run.font.color.rgb = subtitle_color
        paragraph.alignment = _alignment_value(getattr(getattr(profile, "caption_style", None), "align", "left"))
    else:
        run.font.size = Pt(getattr(getattr(profile, "body_style", None), "font_size", 16) or 16)
        run.font.bold = False
        run.font.color.rgb = title_color

    if archetype == "roadmap_overview" and role != "title" and len(content) <= 10:
        run.font.size = Pt(11 if role == "caption" else 12)
        paragraph.alignment = PP_ALIGN.CENTER
    if archetype == "two_column_compare" and content.strip().isdigit() is False and content.startswith("202"):
        run.font.size = Pt(22)
        run.font.bold = True
        run.font.color.rgb = accent_color
        paragraph.alignment = PP_ALIGN.CENTER
    if archetype == "infographic_node_map" and role == "caption":
        run.font.size = Pt(11)
        paragraph.alignment = PP_ALIGN.CENTER
    if archetype == "policy_text_heavy" and role == "title":
        run.font.size = Pt(26)
    if archetype == "closing_statement":
        if role == "title":
            run.font.size = Pt(30)
            run.font.bold = True
        else:
            run.font.size = Pt(18)
        paragraph.alignment = PP_ALIGN.CENTER


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
    rel_x = x0 / pdf_w
    rel_y = y0 / pdf_h
    rel_w = w / pdf_w
    rel_h = h / pdf_h
    left = int(rel_x * ppt_w)
    top = int(rel_y * ppt_h)
    width = int(rel_w * ppt_w)
    height = int(rel_h * ppt_h)
    return left, top, width, height


def _render_text_element(slide, elem, left: int, top: int, width: int, height: int, is_cover_slide: bool) -> None:
    textbox = slide.shapes.add_textbox(left, top, width, height)
    tf = textbox.text_frame
    tf.text = elem.content
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    _apply_text_style(textbox, elem, is_cover_slide)


def _render_picture_element(slide, elem, left: int, top: int, width: int, height: int) -> None:
    img_path = getattr(elem, "path", None)
    if img_path and Path(img_path).exists():
        _add_picture_cover(slide, img_path, left, top, width, height)


def _render_generic_archetype(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    for elem in _sorted_elements_for_render(d_slide):
        if not elem.bbox:
            continue
        left, top, width, height = _element_geometry(elem, pdf_w, pdf_h, ppt_w, ppt_h)
        if elem.type == "text":
            _render_text_element(slide, elem, left, top, width, height, is_cover_slide)
        elif elem.type in {"image", "table"}:
            _render_picture_element(slide, elem, left, top, width, height)


def _render_cover_split(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, True)


def _render_roadmap_overview(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)


def _render_two_column_compare(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)


def _render_policy_text_heavy(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)


def _render_closing_statement(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)


def _render_slide_by_archetype(slide, d_slide, pdf_w: float, pdf_h: float, ppt_w: int, ppt_h: int, is_cover_slide: bool) -> None:
    archetype = getattr(d_slide, "archetype", "single_visual_explainer")
    if archetype == "cover_split":
        _render_cover_split(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h)
        return
    if archetype == "roadmap_overview":
        _render_roadmap_overview(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)
        return
    if archetype == "two_column_compare":
        _render_two_column_compare(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)
        return
    if archetype == "policy_text_heavy":
        _render_policy_text_heavy(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)
        return
    if archetype == "closing_statement":
        _render_closing_statement(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)
        return
    _render_generic_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)


def _add_picture_cover(slide, img_path: str, left: int, top: int, width: int, height: int) -> None:
    with Image.open(img_path) as image:
        image_width, image_height = image.size

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


def generate_pptx(presentation: DomainPresentation, template_key: str = "default", request_id: str | None = None) -> str:
    """
    Convert Domain Presentation to PPTX file.
    Returns path to the generated file.
    """

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

        _render_slide_by_archetype(slide, d_slide, pdf_w, pdf_h, ppt_w, ppt_h, is_cover_slide)

    # Save output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_filename = f"{request_id or 'generated'}_presentation.pptx"
    output_path = OUTPUT_DIR / output_filename
    prs.save(str(output_path))

    
    return str(output_path)
