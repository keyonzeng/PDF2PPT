# AI Agents & Workflows

This document is the project-level guide for AI agents working in the PDF2PPT repository. It is not a cross-project global rule set. It records repository facts, local conventions, and workflow entry points that are relevant inside this workspace.

## Table of Contents

- [Document Scope](#document-scope)
- [How to Read This File](#how-to-read-this-file)
- [Project Overview](#project-overview)
- [Repository Structure](#repository-structure)
- [Implementation Conventions](#implementation-conventions)
- [Testing and Validation Rules](#testing-and-validation-rules)
- [Workflow Catalog](#workflow-catalog)
- [Repository Resources](#repository-resources)
- [Project Notes](#project-notes)

---

## Document Scope

This file is intended to help an agent understand how to work effectively in this repository.

It should be treated as repository-local guidance only. Anything tied to this repository's structure, commands, workflows, or product goals belongs here rather than in a global rule set.

## How to Read This File

- **Use the overview and structure sections** to orient yourself in the repository
- **Use the conventions section** when deciding how to implement or review work here
- **Use `docs/global_testing_rules.md`** for cross-project testing principles that should not live in workspace rules
- **Use the workflow catalog** when a task matches an existing guided procedure
- **Do not assume** the commands, paths, or workflow names here are portable to other repositories

---

## Project Overview

PDF2PPT is a repository for converting PDF documents into structured presentation output.

- **Backend**: Python with `uv`, FastAPI entry points, and MinerU-based PDF processing
- **Frontend**: Next.js application under `frontend/`
- **Root assets**: landing-page style static files such as `index.html`, `styles.css`, and `script.js`
- **Documentation**: specifications, plans, and sample references under `docs/`

## Repository Structure

- `backend/`: API service, tests, MinerU integration, generated outputs, and backend-specific configuration
- `frontend/`: Next.js application and frontend package configuration
- `.agent/workflows/`: repository workflow documents used for guided execution
- `.agent/skills/`: repository-local skills and specialist guidance
- `.shared/ui-ux-pro-max/`: local UI/UX workflow data and scripts
- `assets/prototypes/`: static HTML prototypes and workflow demos kept separate from the main application surfaces
- `docs/`: local planning and reference documents
- Root static files: landing-page assets and lightweight prototypes

### Code Structure Boundaries

- Put backend runtime code under `backend/app/` and keep backend-only scripts or assets under `backend/`
- Put frontend application code under `frontend/src/` and keep framework configuration at the `frontend/` package root
- Keep repository-local skills under `.agent/skills/` when they are part of the checked-in workspace
- Keep workflow definitions under `.agent/workflows/` instead of embedding task procedures in `AGENTS.md`
- Keep one-off HTML demos and internal process prototypes under `assets/prototypes/`
- Keep planning artifacts and reusable reference documents under `docs/`
- Treat root-level static files as landing-page assets, not as the main frontend application structure

## Implementation Conventions

### Architecture and Code Organization

- Keep backend logic simple and functional where possible; prefer straightforward services over unnecessary abstraction
- Treat the technical specs as intent, but verify the actual code paths before editing
- Keep repository guidance aligned with the current workspace rather than aspirational structure
- When adding reusable task procedures, place them in `.agent/workflows/` instead of expanding this file with step-by-step instructions
- Prefer putting new code near the owning domain instead of creating generic shared folders prematurely
- When editing shared modules, inspect downstream consumers before changing names, schemas, or file locations
- Avoid creating new top-level directories unless the existing layout cannot express the ownership clearly
- Keep folder responsibilities explicit: runtime code, static assets, workflow docs, and planning artifacts should not be mixed

### Path-Specific Working Rules

- Changes in `backend/` should preserve the service-oriented layout and use backend validation paths when possible
- Changes in `frontend/` should respect the Next.js package structure and reuse existing UI patterns before adding new ones
- Changes to root `index.html`, `styles.css`, and `script.js` should be treated as landing-page work, separate from the Next.js app
- Changes in `assets/prototypes/` should remain self-contained static demos unless the task explicitly converts them into product code
- Changes in `docs/` should improve discoverability, decision records, or task execution support rather than duplicate repository facts unnecessarily
- Changes in `.agent/skills/` should describe reusable specialist guidance and keep example artifact paths aligned with the repository structure
- Changes in `.agent/workflows/` should describe repeatable procedures, not repository history or business background

### UI Work in This Repository

- Reuse existing UI patterns before introducing new page structures or styling approaches
- Favor responsive layouts, visible interaction states, and motion-safe behavior
- Avoid hover behavior that shifts layout
- Keep UI work consistent with the repository's existing product and landing-page style direction unless the task requires a redesign

## Testing and Validation Rules

### Testing Strategy in This Repository

- Keep a layered test strategy: fast unit tests for local logic, real integration tests for pipeline coordination, and a small number of end-to-end validations for critical user flows
- Do not treat mock-only tests as sufficient proof for PDF upload, MinerU processing, parser conversion, or PPT generation
- Prefer validating observable behavior and generated artifacts over internal implementation details
- Add a regression test for each fixed bug at the lowest layer that still reproduces the real failure mode
- Keep tests deterministic by using stable sample inputs, stable output paths, and explicit assertions on generated artifacts

### Real-Flow Requirements for PDF2PPT

- Backend changes affecting PDF conversion should be validated with a real sample PDF that exercises MinerU, parser conversion, and PPT generation together
- Parser validation should assert the existence of MinerU output folders and `_content_list.json` artifacts before asserting domain model contents
- PPT validation should assert more than file existence when practical, including slide count or representative content extracted from the generated presentation
- Frontend changes affecting upload or conversion should be validated against the local backend with a browser-based flow instead of component-only checks
- External LLM and OAuth providers may be mocked for routine local development, but repository guidance should preserve at least one real-provider validation path outside the default fast test loop

### Test Assets and Commands

- Keep small, stable PDF fixtures and expected artifact references under repository-managed paths rather than relying on ad hoc local files
- Keep generated test outputs under backend-owned output directories so they can be inspected or cleaned consistently
- Prefer directly runnable commands that match the current repository layout; do not rely on implicit module path assumptions

---

## Workflow Catalog

### Existing Repository Workflows

- **MinerU Workflow**: `.agent/workflows/mineru-skills.md`
  - Use for PDF parsing, OCR, extraction, and MinerU-related preparation work.
- **UI/UX Pro Max**: `.agent/workflows/ui-ux-pro-max.md`
  - Use for UI design, redesign, and higher-quality visual implementation work.

### Core Repository Workflows

- **Feature Implementation**: `.agent/workflows/feature-implementation.md`
  - Use for implementing a feature with repo discovery, focused edits, and lightweight validation.
- **Bug Investigation**: `.agent/workflows/bug-investigation.md`
  - Use for root-cause debugging before editing code.
- **UI Change**: `.agent/workflows/ui-change.md`
  - Use for page, component, style, and UX refinements in this repository.
- **Repo Discovery**: `.agent/workflows/repo-discovery.md`
  - Use when entering an unfamiliar area of the codebase and locating authoritative logic.

---

## Repository Resources

- **Workflow Directory**: `.agent/workflows/`
- **Skill Directory**: `.agent/skills/`
- **Global Testing Rules Template**: `docs/global_testing_rules.md`
- **UI/UX Database**: `.shared/ui-ux-pro-max/data/`
- **Search Scripts**: `.shared/ui-ux-pro-max/scripts/`
- **Prototype Demos**: `assets/prototypes/`
- **Backend README**: `backend/README.md`
- **Frontend README**: `frontend/README.md`
- **Technical Specs**: `docs/specs/`
- **Examples**: `docs/examples/`

## Project Notes

### Commands and Validation Paths

- **Backend install**: `uv sync`
- **Backend dev server**: `uv run uvicorn app.main:app --reload`
- **Backend parser test**: `$env:PYTHONPATH='.'; uv run python tests/test_parser.py`
- **Backend PPT test**: `$env:PYTHONPATH='.'; uv run python tests/test_ppt_gen.py`
- **Frontend dev server**: `npm run dev`

### Workflow Maintenance

When adding or updating a workflow in this repository:

1. Create or update the workflow file in `.agent/workflows/`
2. Use YAML frontmatter with a `description` field
3. Keep the instructions specific and actionable
4. Use `// turbo` or `// turbo-all` annotations only where appropriate
5. Update this file so the workflow remains discoverable

### Current Limits

- The repository currently has workflow documents under `.agent/workflows/`.
- The repository currently has local skills under `.agent/skills/`.
- Repository guidance should reflect the current workspace state instead of assuming future folders exist.

### Historical Context

#### Landing Page (January 2026)

**Created**: Professional SaaS landing page for PDF2PPT
**Workflow Used**: `/ui-ux-pro-max`
**Tech Stack**: HTML, CSS, JavaScript (vanilla)
**Design Style**: Modern glassmorphism with blue/purple gradient palette

**Features**:
- Floating glassmorphic navigation
- Hero section with gradient text and stats animation
- 6 feature cards with custom gradient icons
- 3-tier pricing section (Free, Pro, Enterprise)
- Customer testimonials
- Responsive design (mobile-first)
- Smooth scroll animations
- Parallax effects
- Accessibility compliant

**Files Created**:
- `index.html` - Main landing page
- `styles.css` - Modern CSS with variables and animations
- `script.js` - Interactive JavaScript features
- `assets/hero-mockup.png` - AI-generated product mockup

**Design Decisions**:
- Used Inter font family for professional look
- Blue/Purple gradient palette for SaaS credibility
- Dark mode with glassmorphism for premium feel
- Micro-animations for engagement
- Hero-centric layout for conversion optimization

---

**Last Updated**: March 9, 2026  
**Project**: PDF2PPT - Transform PDFs into Beautiful Presentations

