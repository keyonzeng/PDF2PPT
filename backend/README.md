# PDF2PPT Backend

## Engineering Principles
- **Minimalism**: Write useful code only. Avoid over-engineering.
- **No Backward Compatibility**: If code is useless or buggy, delete or rewrite it. Do not keep it for legacy reasons.
- **Structural Simplicity**: Prefer simple functions over classes where state is not required.
- **Spec Driven**: Ensure documentation and specs reflect the code reality.

## Description
Backend service for converting PDFs to PPT content using Mineru for parsing and extraction.

## Installation
Requires `uv` for dependency management.

```bash
uv sync
```

## Usage

### Run Server
```bash
uv run uvicorn app.main:app --reload
```

### Run CLI
```bash
uv run pdf2ppt input.pdf -o output.pptx
```

### CLI Options
- `--template default`
- `--request-id <id>`
- `--output-root <path>`: mirror MinerU artifacts after success
- `--enable-llm`
- `--json`

### Run Tests
```bash
uv run python -m tests.test_parser
```
