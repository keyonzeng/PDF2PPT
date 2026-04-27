# Cover Fidelity Repair Plan

## Goal
Improve PPT-derived PDF conversion fidelity by reducing text layout drift, preserving source line structure, and estimating text style from geometry when direct PDF span styles are unavailable.

## Findings
- Current parser behavior maps MinerU blocks one-by-one into slide elements without regrouping adjacent text blocks.
- Current render mode defaults rely only on text/image counts, which misclassifies PPT-derived pages and overuses `hybrid_overlay`.
- Current PPT generation often falls back to generic bbox replay, which preserves raw fragments instead of slide structure.
- The `openclaw` case works mainly because its page structure already resembles clean slides with low element counts.
- Current parser drops line structure and style hints from MinerU `middle.json`, so PPT text boxes reflow differently from the source PDF.
- Current PPT text styling uses fixed theme sizes and colors, which causes visible mismatches in size, color, and placement on PPT-derived PDFs.
- The local environment currently lacks `PyMuPDF`, so direct PDF span style extraction is not available for this iteration.

## Scope
- Merge adjacent text blocks for PPT-like pages before rendering.
- Recalculate default render modes using page complexity and slide-likeness signals.
- Preserve PPT-like pages with image-first rendering instead of destructive hybrid overlay.
- Remove unnecessary large MinerU response logging that adds I/O overhead.
- Preserve original MinerU line breaks and derive text box content from line structure instead of flattening to one wrapped paragraph.
- Estimate font size and alignment from block and line geometry to better match source text appearance.
- Reduce PPT text frame layout side effects that shift text position away from source bboxes.

## Milestones
1. Add parser-side text block merging and slide-likeness heuristics for PPT-derived pages.
2. Rework review-time render mode defaults to prefer fidelity-preserving modes for complex PPT-like pages.
3. Add a PPT-like render branch that preserves a full-page visual with limited title overlays.
4. Preserve line structure and infer text style from geometry for closer PDF-to-PPT text fidelity.
5. Run focused validation against `openclaw` and the current problematic PPT-derived PDF.


