from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from app.main import _apply_llm_enhancement
from app.services.mineru_service import process_pdf
from app.services.parser_service import parse_mineru_output
from app.services.ppt_gen_service import generate_pptx


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2ppt",
        description="Convert a PDF into a PPTX using the MinerU -> Parser -> PPT pipeline.",
    )
    parser.add_argument("input_pdf", type=Path, help="Path to the input PDF file")
    parser.add_argument("-o", "--output", type=Path, help="Output PPTX path")
    parser.add_argument("--request-id", type=str, default=None, help="Request id for request-scoped artifacts")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional directory to mirror MinerU artifacts after a successful run",
    )
    parser.add_argument("--template", default="default", help="PPT template key")
    parser.add_argument("--enable-llm", action="store_true", help="Enable speaker note generation")
    parser.add_argument("--llm-provider", default=None, help="LLM provider name")
    parser.add_argument("--llm-model", default="", help="LLM model name")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    return parser


def _default_output_path(input_pdf: Path) -> Path:
    return input_pdf.with_suffix(".pptx")


def _materialize_output(generated_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if generated_path.resolve() == output_path.resolve():
        return output_path
    shutil.copy2(generated_path, output_path)
    return output_path


def convert_pdf(
    input_pdf: Path,
    *,
    output_path: Path | None = None,
    request_id: str | None = None,
    output_root: Path | None = None,
    template: str = "default",
    enable_llm: bool = False,
    llm_provider: str | None = None,
    llm_model: str = "",
) -> dict[str, Any]:
    resolved_input = input_pdf.expanduser().resolve()
    if not resolved_input.exists():
        raise FileNotFoundError(f"Input PDF not found: {resolved_input}")
    if resolved_input.suffix.lower() != ".pdf":
        raise ValueError(f"Input file is not a PDF: {resolved_input}")

    resolved_request_id = request_id or uuid.uuid4().hex
    resolved_output_path = output_path or _default_output_path(resolved_input)

    process_result = process_pdf(str(resolved_input), request_id=resolved_request_id)
    if process_result["status"] == "error":
        raise RuntimeError(process_result.get("error") or "Mineru processing failed")

    presentation = parse_mineru_output(process_result["output_folder"])
    _apply_llm_enhancement(presentation, enable_llm, llm_provider, llm_model)

    actual_output_folder = Path(process_result["output_folder"])
    resolved_output_root = Path(process_result.get("output_root") or actual_output_folder.parent)
    if output_root is not None:
        resolved_output_root = output_root.expanduser().resolve()
        mirrored_output_folder = resolved_output_root / actual_output_folder.name
        mirrored_output_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(actual_output_folder, mirrored_output_folder, dirs_exist_ok=True)
    generated_pptx_path = Path(
        generate_pptx(
            presentation,
            template_key=template,
            request_id=resolved_request_id,
            source_pdf_path=str(resolved_input),
        )
    )
    final_pptx_path = _materialize_output(generated_pptx_path, resolved_output_path)

    return {
        "status": "success",
        "input_pdf": str(resolved_input),
        "output_pptx": str(final_pptx_path),
        "generated_pptx": str(generated_pptx_path),
        "output_folder": process_result.get("output_folder"),
        "output_root": str(resolved_output_root),
        "request_id": resolved_request_id,
        "template": template,
        "mineru_result": process_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = convert_pdf(
            args.input_pdf,
            output_path=args.output,
            request_id=args.request_id,
            output_root=args.output_root,
            template=args.template,
            enable_llm=args.enable_llm,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        error_payload = {
            "status": "error",
            "error": str(exc),
        }
        if args.json:
            print(json.dumps(error_payload, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        error_payload = {
            "status": "error",
            "error": str(exc),
        }
        if args.json:
            print(json.dumps(error_payload, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Input PDF: {result['input_pdf']}")
        print(f"MinerU output folder: {result['output_folder']}")
        print(f"PPTX output: {result['output_pptx']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
