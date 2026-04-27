from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, _run_review_job
import app.main as main_module


client = TestClient(app)


class DummyUploadFile:
    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self.file = BytesIO(payload)


def test_run_review_job_persists_runtime_error_details(tmp_path, monkeypatch):
    request_id = "review-error-test"
    state_dir = tmp_path / "review_state"
    state_dir.mkdir(parents=True)

    monkeypatch.setattr(main_module, "REVIEW_STATE_DIR", state_dir)
    monkeypatch.setattr(main_module, "_review_state_path", lambda current_request_id: state_dir / f"{current_request_id}.json")
    monkeypatch.setattr(main_module, "_presentation_state_path", lambda current_request_id: state_dir / f"{current_request_id}.presentation.json")

    main_module._initialize_review_state(request_id, "sample.pdf", f"{request_id}_sample.pdf", str(tmp_path / request_id))

    stored_file_path = tmp_path / f"{request_id}_sample.pdf"
    stored_file_path.write_bytes(b"%PDF-1.4\n")

    def _raise_runtime_error(*args, **kwargs):
        raise RuntimeError("tensor size mismatch from MinerU")

    monkeypatch.setattr(main_module, "_run_conversion_pipeline", _raise_runtime_error)

    _run_review_job(stored_file_path, request_id, "sample.pdf", stored_file_path.name)

    state = main_module._load_review_state(request_id)
    assert state["review_status"]["status"] == "failed"
    assert state["review_status"]["stage"] == "conversion"
    assert state["review_status"]["error"] == "tensor size mismatch from MinerU"


def test_upload_endpoint_uses_request_scoped_output_root(monkeypatch):
    captured = {}

    def _fake_process_pdf(input_file_path: str, model: str = "auto", request_id: str | None = None, output_root: str | None = None):
        captured["input_file_path"] = input_file_path
        captured["request_id"] = request_id
        captured["output_root"] = output_root
        return {
            "status": "success",
            "output_folder": output_root,
            "output_root": output_root,
            "logs": "ok",
            "request_id": request_id,
        }

    monkeypatch.setattr(main_module, "process_pdf", _fake_process_pdf)

    response = client.post(
        "/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4\n", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == captured["request_id"]
    assert captured["output_root"] == str(main_module.OUTPUT_DIR / captured["request_id"])
    assert body["mineru_result"]["output_root"] == captured["output_root"]
    assert Path(captured["input_file_path"]).name == f"{captured['request_id']}_sample.pdf"
