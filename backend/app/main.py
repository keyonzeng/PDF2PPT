import json
import time
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import asyncio
import shutil
import uuid
from pathlib import Path

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="PDF2PPT API", version="1.0.0", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.services.mineru_service import process_pdf
from app.services.parser_service import parse_mineru_output
from app.services.ppt_gen_service import generate_pptx
from app.services.llm_service import generate_speaker_notes
from app.core.models import Presentation

@app.get("/")
async def root():
    return {"message": "PDF2PPT API is running"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "mineru": "cli"}

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "mineru_output"
REVIEW_STATE_DIR = OUTPUT_DIR / "_review_state"
ALLOWED_EXTENSIONS = {".pdf"}
RENDER_MODES = {"auto", "editable", "image_fallback", "hybrid_overlay"}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_STATE_DIR.mkdir(parents=True, exist_ok=True)


class SlideOverride(BaseModel):
    page_id: int
    render_mode: str


class GenerateReviewRequest(BaseModel):
    request_id: str
    template: str = "default"
    overrides: list[SlideOverride] = Field(default_factory=list)


def _now_timestamp() -> float:
    return time.time()


def _new_job_status(status: str, stage: str, message: str, error: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "status": status,
        "stage": stage,
        "message": message,
        "updated_at": _now_timestamp(),
        "error": error,
    }
    if extra:
        payload.update(extra)
    return payload


def _review_state_path(request_id: str) -> Path:
    return REVIEW_STATE_DIR / f"{request_id}.json"


def _presentation_state_path(request_id: str) -> Path:
    return REVIEW_STATE_DIR / f"{request_id}.presentation.json"


def _presentation_summary(presentation, request_id: str, filename: str, output_folder: str) -> dict[str, Any]:
    slides = []
    for slide in presentation.slides:
        text_count = sum(1 for element in slide.elements if element.type == "text")
        image_count = sum(1 for element in slide.elements if element.type == "image")
        table_count = sum(1 for element in slide.elements if element.type == "table")
        element_count = len(slide.elements)
        short_text_count = sum(
            1
            for element in slide.elements
            if element.type == "text" and len(getattr(element, "content", "").strip()) <= 80
        )
        fragmented_text = text_count >= 6 and short_text_count >= max(4, text_count - 1)
        high_complexity = element_count >= 12 or text_count >= 8 or table_count >= 1
        default_render_mode = "auto"
        if slide.page_id == 1 and image_count == 0 and text_count <= 3:
            default_render_mode = "image_fallback"
        if image_count > 0 and fragmented_text and high_complexity:
            default_render_mode = "image_fallback"

        slide.render_mode = default_render_mode
        slides.append(
            {
                "page_id": slide.page_id,
                "archetype": slide.archetype,
                "width": slide.width,
                "height": slide.height,
                "element_count": element_count,
                "text_count": text_count,
                "image_count": image_count,
                "table_count": table_count,
                "default_render_mode": default_render_mode,
                "current_render_mode": default_render_mode,
                "confidence": {
                    "archetype": 0.8,
                    "render_mode": 0.65 if default_render_mode != "auto" else 0.55,
                    "semantic_roles": 0.7 if text_count > 0 else 0.5,
                },
            }
        )

    return {
        "request_id": request_id,
        "filename": filename,
        "output_folder": output_folder,
        "slide_count": len(slides),
        "slides": slides,
    }


def _write_json_state(path: Path, payload: dict[str, Any], request_id: str, stage: str) -> None:
    write_started_at = time.perf_counter()
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    write_elapsed_ms = (time.perf_counter() - write_started_at) * 1000
    file_size_bytes = path.stat().st_size if path.exists() else 0
    print(f"[perf] request_id={request_id} stage={stage} elapsed_ms={write_elapsed_ms:.2f} bytes={file_size_bytes}")


def _read_json_state(path: Path, request_id: str, stage: str) -> dict[str, Any]:
    read_started_at = time.perf_counter()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Review state not found")
    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    read_elapsed_ms = (time.perf_counter() - read_started_at) * 1000
    file_size_bytes = path.stat().st_size if path.exists() else 0
    print(f"[perf] request_id={request_id} stage={stage} elapsed_ms={read_elapsed_ms:.2f} bytes={file_size_bytes}")
    return state


def _save_review_state(request_id: str, state: dict[str, Any]) -> None:
    review_payload = {
        "request_id": state.get("request_id", request_id),
        "filename": state.get("filename", ""),
        "stored_filename": state.get("stored_filename", ""),
        "output_folder": state.get("output_folder", ""),
        "output_root": state.get("output_root", ""),
        "review": state.get("review", {}),
        "last_generated_pptx": state.get("last_generated_pptx"),
        "review_status": state.get("review_status"),
        "generate_status": state.get("generate_status"),
    }
    presentation_value = state.get("presentation") if "presentation" in state else None
    if presentation_value is None:
        presentation_path = _presentation_state_path(request_id)
        if presentation_path.exists():
            existing_presentation_state = _read_json_state(presentation_path, request_id, "load_existing_presentation_state")
            presentation_value = existing_presentation_state.get("presentation")
    presentation_payload = {
        "request_id": state.get("request_id", request_id),
        "presentation": presentation_value,
    }
    _write_json_state(_review_state_path(request_id), review_payload, request_id, "save_review_state")
    _write_json_state(_presentation_state_path(request_id), presentation_payload, request_id, "save_presentation_state")


def _load_review_state(request_id: str) -> dict[str, Any]:
    path = _review_state_path(request_id)
    return _read_json_state(path, request_id, "load_review_state")


def _load_presentation_state(request_id: str) -> dict[str, Any]:
    path = _presentation_state_path(request_id)
    if path.exists():
        return _read_json_state(path, request_id, "load_presentation_state")

    legacy_state = _load_review_state(request_id)
    return {
        "request_id": legacy_state.get("request_id", request_id),
        "presentation": legacy_state.get("presentation"),
    }


def _request_output_root(request_id: str) -> Path:
    return OUTPUT_DIR / request_id


def _initialize_review_state(request_id: str, filename: str, stored_filename: str, output_root: str) -> None:
    _save_review_state(
        request_id,
        {
            "request_id": request_id,
            "filename": filename,
            "stored_filename": stored_filename,
            "output_root": output_root,
            "review": {},
            "review_status": _new_job_status("queued", "review", "Review job queued"),
            "generate_status": _new_job_status("idle", "generate", "Generation not started"),
        },
    )


def _mark_review_status(request_id: str, status: str, stage: str, message: str, error: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    state = _load_review_state(request_id)
    state["review_status"] = _new_job_status(status, stage, message, error, extra)
    _save_review_state(request_id, state)
    return state


def _mark_generate_status(request_id: str, status: str, stage: str, message: str, error: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    state = _load_review_state(request_id)
    state["generate_status"] = _new_job_status(status, stage, message, error, extra)
    _save_review_state(request_id, state)
    return state


def _apply_llm_enhancement(presentation, enable_llm: bool, llm_provider: str | None, llm_model: str) -> None:
    if not enable_llm:
        return

    print("Enhancing with LLM...")
    for slide in presentation.slides:
        text_content = " ".join([e.content for e in slide.elements if e.type == "text"])
        if text_content:
            notes = generate_speaker_notes(text_content, provider=llm_provider, model=llm_model)
            setattr(slide, "speaker_notes", notes)


def _run_conversion_pipeline(
    stored_file_path: Path,
    request_id: str,
    enable_llm: bool = False,
    llm_provider: str | None = None,
    llm_model: str = "",
    output_root: Path | None = None,
):
    pipeline_started_at = time.perf_counter()
    mineru_started_at = time.perf_counter()
    resolved_output_root = output_root or _request_output_root(request_id)
    process_res = process_pdf(str(stored_file_path), request_id=request_id, output_root=str(resolved_output_root))
    mineru_elapsed_ms = (time.perf_counter() - mineru_started_at) * 1000
    print(f"[perf] request_id={request_id} stage=mineru_run elapsed_ms={mineru_elapsed_ms:.2f}")
    if process_res["status"] == "error":
        raise RuntimeError(process_res.get("error") or "Mineru processing failed")

    parse_started_at = time.perf_counter()
    presentation = parse_mineru_output(process_res["output_folder"])
    presentation.metadata["source_pdf_path"] = str(stored_file_path)
    parse_elapsed_ms = (time.perf_counter() - parse_started_at) * 1000
    print(f"[perf] request_id={request_id} stage=parse_mineru_output elapsed_ms={parse_elapsed_ms:.2f}")

    llm_started_at = time.perf_counter()
    _apply_llm_enhancement(presentation, enable_llm, llm_provider, llm_model)
    llm_elapsed_ms = (time.perf_counter() - llm_started_at) * 1000
    total_elapsed_ms = (time.perf_counter() - pipeline_started_at) * 1000
    print(f"[perf] request_id={request_id} stage=apply_llm elapsed_ms={llm_elapsed_ms:.2f}")
    print(f"[perf] request_id={request_id} stage=conversion_pipeline elapsed_ms={total_elapsed_ms:.2f}")
    return presentation, process_res


def _run_review_job(
    stored_file_path: Path,
    request_id: str,
    original_name: str,
    stored_filename: str,
    enable_llm: bool = False,
    llm_provider: str | None = None,
    llm_model: str = "",
) -> None:
    try:
        _mark_review_status(request_id, "running", "conversion", "Running review conversion pipeline")
        presentation, process_res = _run_conversion_pipeline(
            stored_file_path,
            request_id,
            enable_llm,
            llm_provider,
            llm_model,
        )
        summary = _presentation_summary(presentation, request_id, original_name, process_res["output_folder"])
        current_state = _load_review_state(request_id)
        _save_review_state(
            request_id,
            {
                **current_state,
                "filename": original_name,
                "stored_filename": stored_filename,
                "output_folder": process_res["output_folder"],
                "output_root": process_res.get("output_root", current_state.get("output_root", "")),
                "presentation": presentation.model_dump(),
                "review": summary,
                "review_status": _new_job_status("completed", "review", f"Review ready for {summary['slide_count']} slides."),
            },
        )
    except RuntimeError as exc:
        _mark_review_status(request_id, "failed", "conversion", "Mineru processing failed", str(exc))
    except FileNotFoundError as exc:
        _mark_review_status(request_id, "failed", "parse", "Parsing failed", str(exc))
    except Exception as exc:
        _mark_review_status(request_id, "failed", "review", "Review preparation failed", str(exc))


def _run_generate_job(request_id: str, template: str, valid_overrides: dict[int, str]) -> None:
    try:
        state = _mark_generate_status(request_id, "running", "generate", "Generating PPTX")
        presentation_state = _load_presentation_state(request_id)
        presentation_payload = presentation_state.get("presentation")
        if not presentation_payload:
            raise FileNotFoundError("Presentation payload not found")

        presentation = Presentation.model_validate(presentation_payload)
        ppt_started_at = time.perf_counter()
        pptx_path = generate_pptx(
            presentation,
            template_key=template,
            request_id=request_id,
            render_mode_overrides=valid_overrides,
            source_pdf_path=presentation.metadata.get("source_pdf_path"),
        )
        ppt_elapsed_ms = (time.perf_counter() - ppt_started_at) * 1000
        print(f"[perf] request_id={request_id} stage=generate_pptx elapsed_ms={ppt_elapsed_ms:.2f}")

        review = state.get("review", {})
        for slide in review.get("slides", []):
            if slide["page_id"] in valid_overrides:
                slide["current_render_mode"] = valid_overrides[slide["page_id"]]

        _save_review_state(
            request_id,
            {
                **state,
                "presentation": presentation_payload,
                "review": review,
                "last_generated_pptx": pptx_path,
                "generate_status": _new_job_status(
                    "completed",
                    "generate",
                    "PPTX generated successfully",
                    extra={
                        "download_url": f"/download/{request_id}",
                        "overrides_applied": len(valid_overrides),
                    },
                ),
            },
        )
    except FileNotFoundError as exc:
        _mark_generate_status(request_id, "failed", "generate", "Presentation payload not found", str(exc))
    except Exception as exc:
        _mark_generate_status(request_id, "failed", "generate", "PPT generation failed", str(exc))

def _sanitize_filename(filename: str) -> str:
    candidate = Path(filename or "upload.pdf").name
    if not candidate:
        raise HTTPException(status_code=400, detail="Invalid filename")

    extension = Path(candidate).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    return candidate

def _save_upload(file: UploadFile, request_id: str) -> tuple[str, Path]:
    safe_name = _sanitize_filename(file.filename or "upload.pdf")
    stored_name = f"{request_id}_{safe_name}"
    file_path = UPLOAD_DIR / stored_name

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    return safe_name, file_path

def _error_response(message: str, request_id: str) -> dict:
    return {"error": message, "request_id": request_id}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex
    original_name, stored_file_path = _save_upload(file, request_id)
    output_root = str(_request_output_root(request_id))

    result = await asyncio.to_thread(process_pdf, str(stored_file_path), request_id=request_id, output_root=output_root)
    if result["status"] == "error":
        return _error_response("Mineru processing failed", request_id)

    return {
        "id": request_id,
        "filename": original_name,
        "stored_filename": stored_file_path.name,
        "message": "Mineru processing complete.",
        "mineru_result": result,
    }

@app.post("/convert")
async def convert_pdf(
    file: UploadFile = File(...), 
    template: str = Form("default"),
    enable_llm: bool = Form(False),
    llm_provider: str = Form(None),
    llm_model: str = Form("")
):
    """
    Full pipeline: Upload -> Process -> Parse -> (LLM) -> Generate PPTX
    """
    request_id = uuid.uuid4().hex
    original_name, stored_file_path = _save_upload(file, request_id)

    try:
        presentation, _ = await asyncio.to_thread(
            _run_conversion_pipeline,
            stored_file_path,
            request_id,
            enable_llm,
            llm_provider,
            llm_model,
        )
        pptx_path = await asyncio.to_thread(generate_pptx, presentation, template_key=template, request_id=request_id)
    except RuntimeError:
        return _error_response("Mineru processing failed", request_id)
    except FileNotFoundError:
        return _error_response("Parsing failed", request_id)
    except Exception:
        return _error_response("PPT generation failed", request_id)

    return FileResponse(
        pptx_path, 
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", 
        filename=f"{Path(original_name).stem}.pptx"
    )


@app.post("/convert/review")
async def convert_pdf_for_review(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    enable_llm: bool = Form(False),
    llm_provider: str = Form(None),
    llm_model: str = Form(""),
):
    request_id = uuid.uuid4().hex
    original_name, stored_file_path = _save_upload(file, request_id)
    output_root = str(_request_output_root(request_id))
    _initialize_review_state(request_id, original_name, stored_file_path.name, output_root)
    background_tasks.add_task(
        _run_review_job,
        stored_file_path,
        request_id,
        original_name,
        stored_file_path.name,
        enable_llm,
        llm_provider,
        llm_model,
    )
    return {
        "request_id": request_id,
        "status": "queued",
        "status_url": f"/status/{request_id}",
    }


@app.get("/review/{request_id}")
async def get_review_state(request_id: str):
    state = _load_review_state(request_id)
    return state["review"]


@app.get("/status/{request_id}")
async def get_job_status(request_id: str):
    state = _load_review_state(request_id)
    return {
        "request_id": request_id,
        "filename": state.get("filename", ""),
        "review_status": state.get("review_status"),
        "generate_status": state.get("generate_status"),
        "review": state.get("review") or None,
        "download_url": f"/download/{request_id}" if state.get("last_generated_pptx") else None,
    }


@app.post("/generate")
async def generate_from_review(request: GenerateReviewRequest, background_tasks: BackgroundTasks):
    state = _load_review_state(request.request_id)
    review = state.get("review", {})
    if not review:
        raise HTTPException(status_code=409, detail="Review is not ready")

    current_modes = {
        slide.get("page_id"): slide.get("current_render_mode", slide.get("default_render_mode", "auto"))
        for slide in review.get("slides", [])
    }
    valid_overrides = {
        override.page_id: override.render_mode
        for override in request.overrides
        if override.render_mode in RENDER_MODES
        and current_modes.get(override.page_id, "auto") != override.render_mode
    }
    _mark_generate_status(
        request.request_id,
        "queued",
        "generate",
        "Generation job queued",
        extra={"overrides_applied": len(valid_overrides)},
    )
    background_tasks.add_task(_run_generate_job, request.request_id, request.template, valid_overrides)
    return {
        "request_id": request.request_id,
        "status": "queued",
        "status_url": f"/status/{request.request_id}",
        "overrides_applied": len(valid_overrides),
    }


@app.get("/download/{request_id}")
async def download_generated_pptx(request_id: str):
    state = _load_review_state(request_id)
    pptx_path = state.get("last_generated_pptx")
    if not pptx_path or not Path(pptx_path).exists():
        raise HTTPException(status_code=404, detail="Generated PPTX not found")

    filename = f"{Path(state.get('filename', 'presentation.pdf')).stem}.pptx"
    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )
