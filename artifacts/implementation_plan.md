# Cover Fidelity Repair Plan

## Goal
Improve visual fidelity for the full `backend/uploads/openclaw.pdf` document by analyzing page-level failures in `backend/mineru_output/openclaw-output.pdf` and replacing static PPT templates with PDF-style-derived slide construction.

## Findings
- The generated PPT now preserves basic element placement, but document-wide layout fidelity still depends on generic slide assumptions rather than page-specific PDF style signals.
- The source PDF pages are image-heavy and many pages expose no embedded text at the PDF layer, so MinerU middle data is the practical authoritative source for structure and page geometry.
- Static template selection is the wrong abstraction for this workload because the source deck already contains its own visual system: page size, title zones, content density, image anchoring, and recurring section layouts.
- The remaining failures are primarily typographic hierarchy, spacing rhythm, grouping, and page archetype reconstruction rather than raw content extraction.

## Scope
- Produce a page-by-page issue analysis for the original and generated openclaw outputs.
- Derive reusable page archetypes and style tokens from the PDF instead of loading a static PPT template.
- Extend the parser and generator to carry enough style/layout metadata for dynamic slide construction.
- Re-run real pipeline validation and inspect representative pages across all archetypes.

## Milestones
1. Build a page-by-page problem matrix for all 30 pages and group them into archetypes.
2. Extract PDF-derived style tokens and layout rules instead of relying on static template files.
3. Refactor slide generation to synthesize per-page layouts from archetype rules and parsed geometry.
4. Validate representative pages from each archetype with the real openclaw pipeline output.
