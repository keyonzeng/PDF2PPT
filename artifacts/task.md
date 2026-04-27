# Backend Performance Optimization Task

Repair PPT-derived PDF conversion fidelity by reducing parser fragmentation, improving render mode defaults, and restoring source-like text size, color, line breaks, and positioning during PPT generation.

## In Scope

- `backend/app/main.py`
- `backend/app/core/models.py`
- `backend/app/services/parser_service.py`
- `backend/app/services/ppt_gen_service.py`
- Focused validation against `openclaw` and the current problematic PPT-derived PDF

## Target Outcomes

- Adjacent text fragments are merged before slide rendering when pages are PPT-like.
- Default render modes avoid destructive `hybrid_overlay` behavior on complex slide pages.
- PPT-like pages preserve a full-page visual with limited text overlays instead of fragmented bbox replay.
- Review and generate output become more faithful for PPT-to-PDF inputs.
- Generated text boxes preserve source line structure instead of collapsing into reflowed paragraphs.
- Generated text size, alignment, and color move closer to the source document using geometry-driven heuristics.
