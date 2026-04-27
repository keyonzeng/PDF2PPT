import subprocess
import sys
import time
from pathlib import Path

from app.core.config import settings

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "mineru_output"


def _has_mineru_artifacts(folder: Path) -> bool:
    if not folder.exists() or not folder.is_dir():
        return False
    if next(folder.rglob("*_content_list.json"), None):
        return True
    if next(folder.rglob("*_middle.json"), None):
        return True
    return False


def _candidate_output_folders(input_file: Path, request_id: str | None, output_root: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def _add_candidate(path: Path) -> None:
        if path in seen:
            return
        seen.add(path)
        candidates.append(path)

    _add_candidate(output_root / input_file.stem)

    if request_id:
        prefix = f"{request_id}_"
        if input_file.stem.startswith(prefix):
            original_stem = input_file.stem[len(prefix):]
            if original_stem:
                _add_candidate(output_root / original_stem)

                for path in output_root.glob(f"{request_id}_*"):
                    if path.is_dir():
                        _add_candidate(path)

                for path in output_root.glob(f"*{original_stem}"):
                    if path.is_dir():
                        _add_candidate(path)

    return candidates


def _resolve_output_folder(
    input_file: Path,
    request_id: str | None,
    output_root: Path,
    parse_method: str,
) -> Path | None:
    for candidate in _candidate_output_folders(input_file, request_id, output_root):
        if _has_mineru_artifacts(candidate):
            return candidate

    direct_candidate = output_root / input_file.stem / parse_method
    if _has_mineru_artifacts(direct_candidate):
        return direct_candidate

    if request_id:
        return None

    artifact_candidates: list[Path] = []
    seen: set[Path] = set()
    for pattern in ("*_content_list.json", "*_middle.json"):
        for artifact_path in output_root.rglob(pattern):
            artifact_parent = artifact_path.parent
            if artifact_parent in seen:
                continue
            seen.add(artifact_parent)
            artifact_candidates.append(artifact_parent)

    if artifact_candidates:
        artifact_candidates.sort(key=lambda path: len(path.parts), reverse=True)
        return artifact_candidates[0]

    return None


def process_pdf(input_file_path: str, model: str = "auto", request_id: str | None = None, output_root: str | None = None) -> dict:
    """
    Runs MinerU parsing for a PDF and resolves artifact output folder.
    
    Args:
        input_file_path: Absolute path to the uploaded PDF file
        model: Reserved compatibility parameter
        request_id: Request identifier used for request-scoped artifact resolution
        output_root: Optional artifact root directory for MinerU output
    """
    input_file = Path(input_file_path).resolve()
    output_path = Path(output_root).resolve() if output_root else OUTPUT_DIR
    
    # Ensure output directory exists (idempotent)
    output_path.mkdir(exist_ok=True, parents=True)

    if not input_file.exists():
        return {
            "status": "error",
            "error": f"Input PDF not found: {input_file}"
        }

    cached_output_folder = _resolve_output_folder(
        input_file,
        request_id,
        output_path,
        settings.MINERU_API_PARSE_METHOD,
    )
    if cached_output_folder:
        print(f"[perf] mineru cache hit: {cached_output_folder}")
        return {
            "status": "success",
            "output_folder": str(cached_output_folder),
            "output_root": str(output_path),
            "request_id": request_id,
            "cache_hit": True,
        }

    print(f"Running local MinerU parse for: {input_file}")
    
    try:
        started_at = time.perf_counter()
        cmd = [
            sys.executable,
            "-m",
            "app.services.mineru_runner",
            "--input",
            str(input_file),
            "--output",
            str(output_path),
            "--backend",
            settings.MINERU_API_BACKEND,
            "--parse-method",
            settings.MINERU_API_PARSE_METHOD,
            "--lang",
            settings.MINERU_PARSE_LANG,
            "--dump-content-list",
        ]

        subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=settings.MINERU_API_TIMEOUT_SECONDS,
            check=True,
            text=True,
        )
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        print(f"[perf] mineru_runner elapsed_ms={elapsed_ms:.2f} input={input_file.name}")

        output_folder = _resolve_output_folder(
            input_file,
            request_id,
            output_path,
            settings.MINERU_API_PARSE_METHOD,
        )
        if not output_folder:
            return {
                "status": "error",
                "error": f"MinerU output folder with artifacts was not created for {input_file.stem}",
                "output_root": str(output_path),
            }

        return {
            "status": "success",
            "output_folder": str(output_folder),
            "output_root": str(output_path),
            "request_id": request_id,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "error": f"MinerU CLI timed out after {settings.MINERU_API_TIMEOUT_SECONDS}s",
        }
    except subprocess.CalledProcessError as exc:
        stderr_text = (exc.stderr or "").strip()
        return {
            "status": "error",
            "error": stderr_text or f"MinerU CLI failed with exit code {exc.returncode}",
        }
        
    except RuntimeError as e:
        return {
            "status": "error",
            "error": str(e),
        }


