from pathlib import Path

import pdf2ppt_cli as cli_module


BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PDF = BASE_DIR / "uploads" / "TheLastLeaf.pdf"


def test_cli_converts_real_pdf_to_requested_output_path(tmp_path, capsys):
    output_path = tmp_path / "result.pptx"
    output_root = tmp_path / "mineru-output"

    exit_code = cli_module.main(
        [
            str(SAMPLE_PDF),
            "--output",
            str(output_path),
            "--output-root",
            str(output_root),
            "--request-id",
            "cli-real-test",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.exists()
    assert output_root.exists()
    assert any(output_root.rglob("*_content_list.json"))
    assert "PPTX output:" in captured.out
    assert str(output_path) in captured.out


def test_cli_missing_input_fails_fast(tmp_path, capsys):
    missing_pdf = tmp_path / "missing.pdf"

    exit_code = cli_module.main([str(missing_pdf)])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Input PDF not found" in captured.err
