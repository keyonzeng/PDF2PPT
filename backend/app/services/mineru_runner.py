from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.core.config import settings


def _ensure_local_mineru_repo() -> Path:
    repo_path = Path(settings.MINERU_REPO_PATH).expanduser().resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"MinerU repo not found: {repo_path}")
    repo_str = str(repo_path)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)
    return repo_path


_ensure_local_mineru_repo()

from mineru.cli.common import do_parse  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MinerU parse directly from the local repository")
    parser.add_argument("--input", required=True, type=Path, help="Input PDF path")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--request-id", default="", help="Request id for traceability")
    parser.add_argument("--backend", default=settings.MINERU_API_BACKEND, help="MinerU backend")
    parser.add_argument("--parse-method", default=settings.MINERU_API_PARSE_METHOD, help="MinerU parse method")
    parser.add_argument("--lang", default=settings.MINERU_PARSE_LANG, help="MinerU language hint")
    parser.add_argument("--formula-enable", action="store_true", default=settings.MINERU_FORMULA_ENABLE)
    parser.add_argument("--no-formula-enable", action="store_false", dest="formula_enable")
    parser.add_argument("--table-enable", action="store_true", default=settings.MINERU_TABLE_ENABLE)
    parser.add_argument("--no-table-enable", action="store_false", dest="table_enable")
    parser.add_argument("--dump-md", action="store_true", default=settings.MINERU_DUMP_MD)
    parser.add_argument("--dump-content-list", action="store_true", default=settings.MINERU_DUMP_CONTENT_LIST)
    parser.add_argument("--dump-middle-json", action="store_true", default=True)
    parser.add_argument("--dump-model-output", action="store_true", default=settings.MINERU_DUMP_MODEL_OUTPUT)
    parser.add_argument("--dump-orig-pdf", action="store_true", default=settings.MINERU_DUMP_ORIG_PDF)
    parser.add_argument("--draw-layout-bbox", action="store_true", default=settings.MINERU_DRAW_LAYOUT_BBOX)
    parser.add_argument("--draw-span-bbox", action="store_true", default=settings.MINERU_DRAW_SPAN_BBOX)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"MinerU input not found: {input_path}", file=sys.stderr)
        return 1
    if input_path.suffix.lower() != ".pdf":
        print(f"MinerU input is not a PDF: {input_path}", file=sys.stderr)
        return 1

    if settings.MINERU_DEVICE_MODE:
        os.environ["MINERU_DEVICE_MODE"] = settings.MINERU_DEVICE_MODE
    os.environ["MINERU_PROCESSING_WINDOW_SIZE"] = str(settings.MINERU_PROCESSING_WINDOW_SIZE)
    os.environ["MINERU_FORMULA_ENABLE"] = str(args.formula_enable)
    os.environ["MINERU_TABLE_ENABLE"] = str(args.table_enable)

    try:
        do_parse(
            output_path,
            [input_path.stem],
            [input_path.read_bytes()],
            [args.lang],
            backend=args.backend,
            parse_method=args.parse_method,
            formula_enable=args.formula_enable,
            table_enable=args.table_enable,
            server_url=None,
            f_draw_layout_bbox=args.draw_layout_bbox,
            f_draw_span_bbox=args.draw_span_bbox,
            f_dump_md=args.dump_md,
            f_dump_middle_json=args.dump_middle_json,
            f_dump_model_output=args.dump_model_output,
            f_dump_orig_pdf=args.dump_orig_pdf,
            f_dump_content_list=args.dump_content_list,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
