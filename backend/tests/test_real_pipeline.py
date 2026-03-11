from pathlib import Path
from uuid import uuid4

from pptx import Presentation as PptxPresentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.services.mineru_service import process_pdf
from app.services.parser_service import parse_mineru_output
from app.services.ppt_gen_service import generate_pptx


BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PDF = BASE_DIR / "uploads" / "TheLastLeaf.pdf"
OPENCLAW_PDF = BASE_DIR / "uploads" / "openclaw.pdf"


def _generated_content_slides(ppt: PptxPresentation, parsed_slide_count: int):
    assert len(ppt.slides) >= parsed_slide_count, "Generated PPT should include all parsed slides"
    generated_slide_delta = len(ppt.slides) - parsed_slide_count
    assert generated_slide_delta <= 1, "Generated PPT should not introduce more than one template slide"
    return list(ppt.slides)[-parsed_slide_count:]


def _normalize_shape_bbox(shape, slide_width: int, slide_height: int) -> tuple[float, float, float, float]:
    return (
        shape.left / slide_width,
        shape.top / slide_height,
        shape.width / slide_width,
        shape.height / slide_height,
    )


def _normalize_element_bbox(element, slide_width: float, slide_height: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = element.bbox
    return (
        x0 / slide_width,
        y0 / slide_height,
        (x1 - x0) / slide_width,
        (y1 - y0) / slide_height,
    )


def _assert_bbox_close(actual: tuple[float, float, float, float], expected: tuple[float, float, float, float], tolerance: float = 0.03):
    for actual_value, expected_value in zip(actual, expected):
        assert abs(actual_value - expected_value) <= tolerance, (
            f"Bounding box mismatch. actual={actual}, expected={expected}, tolerance={tolerance}"
        )


def _bbox_distance(actual: tuple[float, float, float, float], expected: tuple[float, float, float, float]) -> float:
    return sum(abs(actual_value - expected_value) for actual_value, expected_value in zip(actual, expected))


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _find_text_shape(slide, expected_text: str, expected_bbox: tuple[float, float, float, float], used_shape_ids: set[int], slide_width: int, slide_height: int):
    normalized_expected = " ".join(expected_text.split())
    matched_candidates = []
    for shape in slide.shapes:
        if id(shape) in used_shape_ids:
            continue
        if hasattr(shape, "text") and shape.text:
            normalized_actual = " ".join(shape.text.split())
            if normalized_actual == normalized_expected:
                actual_bbox = _normalize_shape_bbox(shape, slide_width, slide_height)
                matched_candidates.append((shape, _bbox_distance(actual_bbox, expected_bbox)))

    if not matched_candidates:
        return None

    matched_candidates.sort(key=lambda item: item[1])
    return matched_candidates[0][0]


def _picture_shapes(slide):
    return [shape for shape in slide.shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE]


def _run_pipeline(sample_pdf: Path, request_prefix: str):
    assert sample_pdf.exists(), f"Sample PDF not found: {sample_pdf}"

    process_result = process_pdf(str(sample_pdf), request_id=request_prefix)
    assert process_result["status"] == "success", process_result

    output_folder = Path(process_result["output_folder"])
    assert output_folder.exists(), f"MinerU output folder missing: {output_folder}"

    content_list_candidates = list(output_folder.rglob("*_content_list.json"))
    assert content_list_candidates, f"No MinerU content list found under: {output_folder}"

    presentation = parse_mineru_output(str(output_folder))
    request_id = f"{request_prefix}-{uuid4().hex[:8]}"
    pptx_path = Path(generate_pptx(presentation, template_key="default", request_id=request_id))
    assert pptx_path.exists(), f"Generated PPTX missing: {pptx_path}"

    ppt = PptxPresentation(str(pptx_path))
    content_slides = _generated_content_slides(ppt, len(presentation.slides))
    return presentation, ppt, content_slides, output_folder, pptx_path


def test_real_pdf_to_ppt_pipeline():
    presentation, ppt, _, output_folder, pptx_path = _run_pipeline(SAMPLE_PDF, "real-pipeline-test")

    assert output_folder.exists(), f"MinerU output folder missing: {output_folder}"
    assert pptx_path.exists(), f"Generated PPTX missing: {pptx_path}"
    assert len(presentation.slides) >= 2, "Expected at least 2 slides from sample PDF"
    assert any(element.type == "text" for slide in presentation.slides for element in slide.elements), "Expected parsed text elements"

    all_text = []
    for slide in ppt.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                all_text.append(shape.text)

    combined_text = "\n".join(all_text)
    assert "The Last Leaf" in combined_text, "Expected representative title text in generated PPT"


def test_openclaw_pdf_content_and_layout_consistency():
    presentation, ppt, content_slides, output_folder, pptx_path = _run_pipeline(OPENCLAW_PDF, "openclaw-pipeline-test")

    assert output_folder.exists(), f"MinerU output folder missing: {output_folder}"
    assert pptx_path.exists(), f"Generated PPTX missing: {pptx_path}"
    assert presentation.slides, "Expected parsed slides from openclaw.pdf"

    slide_width = ppt.slide_width
    slide_height = ppt.slide_height

    matched_text_count = 0
    matched_picture_count = 0
    total_text_count = 0
    total_picture_like_count = 0

    for parsed_slide, generated_slide in zip(presentation.slides, content_slides):
        expected_text_elements = [
            element for element in parsed_slide.elements if element.type == "text" and element.content.strip() and element.bbox
        ]
        expected_picture_elements = [
            element for element in parsed_slide.elements if element.type in {"image", "table"} and element.bbox
        ]

        total_text_count += len(expected_text_elements)
        total_picture_like_count += len(expected_picture_elements)

        generated_pictures = _picture_shapes(generated_slide)
        assert len(generated_pictures) >= len(expected_picture_elements), (
            "Generated slide should contain at least the parsed image/table elements"
        )

        unused_pictures = generated_pictures.copy()
        generated_text_entries = []
        for shape in generated_slide.shapes:
            if hasattr(shape, "text") and shape.text:
                generated_text_entries.append(
                    {
                        "shape": shape,
                        "text": _normalized_text(shape.text),
                        "bbox": _normalize_shape_bbox(shape, slide_width, slide_height),
                    }
                )
        used_text_entry_indexes = set()

        for element in expected_text_elements:
            expected_bbox = _normalize_element_bbox(element, parsed_slide.width, parsed_slide.height)
            normalized_expected_text = _normalized_text(element.content)
            text_candidates = []
            for entry_index, entry in enumerate(generated_text_entries):
                if entry_index in used_text_entry_indexes:
                    continue
                if entry["text"] == normalized_expected_text:
                    text_candidates.append((entry_index, entry, _bbox_distance(entry["bbox"], expected_bbox)))

            assert text_candidates, f"Missing text element in generated PPT: {element.content[:80]}"
            text_candidates.sort(key=lambda item: item[2])
            matched_entry_index, matched_entry, _ = text_candidates[0]

            _assert_bbox_close(matched_entry["bbox"], expected_bbox)
            used_text_entry_indexes.add(matched_entry_index)
            matched_text_count += 1

        for element in expected_picture_elements:
            expected_bbox = _normalize_element_bbox(element, parsed_slide.width, parsed_slide.height)
            matched_picture = None
            for picture in unused_pictures:
                actual_bbox = _normalize_shape_bbox(picture, slide_width, slide_height)
                if all(abs(actual_value - expected_value) <= 0.03 for actual_value, expected_value in zip(actual_bbox, expected_bbox)):
                    matched_picture = picture
                    break

            assert matched_picture is not None, "Missing image/table element with matching layout in generated PPT"
            unused_pictures.remove(matched_picture)
            matched_picture_count += 1

    assert total_text_count > 0, "Expected parsed text elements from openclaw.pdf"
    assert matched_text_count == total_text_count, "All parsed text elements should be preserved in generated PPT"
    assert matched_picture_count == total_picture_like_count, "All parsed image/table elements should keep layout mapping in generated PPT"
