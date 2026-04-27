from pathlib import Path
from uuid import uuid4

from app.services.fidelity_service import evaluate_presentation_fidelity
from app.services.mineru_service import process_pdf
from app.services.parser_service import parse_mineru_output
from app.services.ppt_gen_service import generate_pptx


BASE_DIR = Path(__file__).resolve().parents[1]
OPENCLAW_PDF = BASE_DIR / "uploads" / "openclaw.pdf"


def test_openclaw_fidelity_score_reaches_90():
    assert OPENCLAW_PDF.exists(), f"Missing fixture PDF: {OPENCLAW_PDF}"

    process_result = process_pdf(str(OPENCLAW_PDF), request_id=f"fidelity-{uuid4().hex[:8]}")
    assert process_result["status"] == "success", process_result

    output_folder = Path(process_result["output_folder"])
    presentation = parse_mineru_output(str(output_folder))
    pptx_path = Path(
        generate_pptx(
            presentation,
            template_key="default",
            request_id=f"fidelity-{uuid4().hex[:8]}",
            source_pdf_path=str(OPENCLAW_PDF),
        )
    )
    assert pptx_path.exists(), f"Generated PPTX missing: {pptx_path}"

    report = evaluate_presentation_fidelity(presentation, pptx_path)
    print("fidelity_report", report)
    print("page_scores", [(slide_report.page_id, round(slide_report.score, 2)) for slide_report in report.slide_reports])

    assert report.score >= 90.0, f"Fidelity score below target: {report.score:.2f}"
    low_pages = [slide_report for slide_report in report.slide_reports if slide_report.score < 90.0]
    assert not low_pages, (
        "Per-slide fidelity score below target: "
        + ", ".join(f"page {slide_report.page_id}={slide_report.score:.2f}" for slide_report in low_pages)
    )
