# PDF2PPT CLI Spec

## Goal

Provide a single command that accepts a PDF path and produces a PPTX file using the existing MinerU -> Parser -> PPT pipeline.

## Command

```bash
pdf2ppt <input.pdf> [options]
```

## Inputs

- `input.pdf`
  - Required positional argument.
  - Must point to an existing PDF file.

## Options

- `-o, --output <path>`
  - Optional output file path.
  - If omitted, write to the same directory as the input PDF with the `.pptx` extension.

- `--request-id <id>`
  - Optional request identifier.
  - If omitted, the CLI generates a stable UUID-like identifier.
  - Used for request-scoped MinerU output folders.

- `--template <name>`
  - Optional PPT template key.
  - Default: `default`.

- `--enable-llm`
  - Optional flag.
  - Default: disabled.
  - When enabled, the pipeline may add speaker notes using the current LLM provider settings.

- `--llm-provider <name>`
  - Optional LLM provider name.
  - Passed through to the current pipeline.

- `--llm-model <name>`
  - Optional LLM model name.
  - Passed through to the current pipeline.

- `--output-root <path>`
  - Optional artifact mirror directory.
  - MinerU still runs through the proven backend pipeline path.
  - After success, the CLI mirrors the MinerU artifact folder into this directory.

- `--json`
  - Optional flag.
  - Print machine-readable JSON result to stdout.

## Behavior

1. Validate that the input PDF exists.
2. Run MinerU parsing using the existing backend pipeline behavior.
3. Parse MinerU artifacts into a `Presentation` object.
4. Generate PPTX using the existing PPT generation service.
5. Write the PPTX to the requested output path.
6. Report the final PPTX path and intermediate output folder.

## Output

### Human-readable mode

Print:
- input PDF path
- MinerU output folder
- generated PPTX path

### JSON mode

Return JSON with:
- `status`
- `input_pdf`
- `output_pptx`
- `output_folder`
- `request_id`
- `template`
- `logs` or error message

## Exit Codes

- `0`: success
- `1`: validation or pipeline failure

## Error Handling

- Missing input PDF: fail fast with clear message.
- MinerU unavailable or parse failure: surface the original error.
- PPT generation failure: surface the original error.

## Non-Goals

- No new conversion logic.
- No reimplementation of MinerU or PPT rendering.
- No GUI wrapper.

## Acceptance Criteria

- A user can run one command to convert a PDF into a PPTX file.
- The CLI reuses the existing pipeline code.
- The CLI supports both human-readable and JSON output.
- The CLI has tests for success and failure paths.
