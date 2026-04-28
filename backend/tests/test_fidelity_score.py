from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import pytest

from app.services.fidelity_service import evaluate_presentation_fidelity
from app.services.mineru_service import process_pdf
from app.services.parser_service import parse_mineru_output
from app.services.ppt_gen_service import generate_pptx


BASE_DIR = Path(__file__).resolve().parents[1]


def _is_pdf_fixture(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.stat().st_size < 1024:
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"%PDF"
    except OSError:
        return False


UPLOAD_PDFS = [path for path in sorted(BASE_DIR.joinpath("uploads").glob("*.pdf")) if _is_pdf_fixture(path)]


@lru_cache(maxsize=None)
def _run_fidelity_pipeline(sample_pdf: Path):
    assert sample_pdf.exists(), f"Missing fixture PDF: {sample_pdf}"

    process_result = process_pdf(str(sample_pdf), request_id=f"fidelity-{sample_pdf.stem}-{uuid4().hex[:8]}")
    assert process_result["status"] == "success", process_result

    output_folder = Path(process_result["output_folder"])
    presentation = parse_mineru_output(str(output_folder))
    pptx_path = Path(
        generate_pptx(
            presentation,
            template_key="default",
            request_id=f"fidelity-{sample_pdf.stem}-{uuid4().hex[:8]}",
            source_pdf_path=str(sample_pdf),
        )
    )
    assert pptx_path.exists(), f"Generated PPTX missing: {pptx_path}"

    report = evaluate_presentation_fidelity(presentation, pptx_path)
    return report, pptx_path


@pytest.mark.parametrize("sample_pdf", UPLOAD_PDFS, ids=lambda path: path.stem)
def test_upload_fidelity_score_reaches_90(sample_pdf: Path):
    assert UPLOAD_PDFS, f"No PDF fixtures found under {BASE_DIR / 'uploads'}"

    report, pptx_path = _run_fidelity_pipeline(sample_pdf)
    print("fidelity_report", report)
    print("page_scores", [(slide_report.page_id, round(slide_report.score, 2)) for slide_report in report.slide_reports])

    assert report.score >= 90.0, f"{sample_pdf.name} fidelity score below target: {report.score:.2f}"
    low_pages = [slide_report for slide_report in report.slide_reports if slide_report.score < 90.0]
    assert not low_pages, (
        f"{sample_pdf.name} per-slide fidelity score below target: "
        + ", ".join(f"page {slide_report.page_id}={slide_report.score:.2f}" for slide_report in low_pages)
    )
