from pathlib import Path

from app.services.mineru_service import _resolve_output_folder


def test_resolve_output_folder_does_not_fall_back_to_unrelated_artifacts_for_request_scoped_root(tmp_path):
    request_id = "req123"
    output_root = tmp_path / request_id
    output_root.mkdir(parents=True)

    unrelated_dir = output_root / "stale_artifact"
    unrelated_dir.mkdir()
    (unrelated_dir / "stale_middle.json").write_text("{}", encoding="utf-8")

    input_file = tmp_path / f"{request_id}_sample.pdf"
    input_file.write_bytes(b"%PDF-1.4\n")

    resolved = _resolve_output_folder(input_file, request_id, output_root)

    assert resolved is None


def test_resolve_output_folder_can_use_generic_fallback_without_request_id(tmp_path):
    output_root = tmp_path / "shared_output"
    artifact_dir = output_root / "nested" / "artifact"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "sample_middle.json").write_text("{}", encoding="utf-8")

    input_file = tmp_path / "sample.pdf"
    input_file.write_bytes(b"%PDF-1.4\n")

    resolved = _resolve_output_folder(input_file, None, output_root)

    assert resolved == artifact_dir
