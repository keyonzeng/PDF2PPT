# Global Testing Rules

This document records cross-project testing principles that should remain portable across repositories.

## Core Principles

- Prefer validating externally observable behavior over internal implementation details.
- Require at least one closed-loop validation path for every user-visible core feature.
- Use mocks only for uncontrollable, high-cost, rate-limited, or security-sensitive external dependencies.
- Keep a layered strategy: fast unit tests, higher-confidence integration tests, and a small number of end-to-end tests for critical flows.
- Add a regression test for every bug fix at the lowest layer that still reproduces the real failure mode.
- Optimize for stable tests over numerous flaky tests.

## Real Integration Guidance

- Do not treat mock-only tests as sufficient proof for workflows that depend on real files, processes, databases, queues, browsers, or service boundaries.
- Prefer real local dependencies, real sample assets, and real protocol boundaries when those dependencies can run deterministically in development or CI.
- When a mock is used, document which real dependency it replaces and why the real path is not part of the default test loop.
- Assert outputs, artifacts, persisted state, API contracts, and user-visible effects rather than only call counts or internal branches.

## Closed-Loop Validation Guidance

- A closed-loop test should exercise the system from realistic input through the main processing path to a final user-consumable result.
- If the product generates artifacts, closed-loop tests should verify artifact creation, structure, and representative contents.
- If the product exposes a UI, at least one validation path should cover real user interaction against a running application rather than component-only assertions.
- If a feature depends on intermediate generated assets, tests should assert those intermediate artifacts before asserting the final output.

## Exceptions Policy

- External AI providers, OAuth providers, payment providers, and other third-party systems may be mocked in the fast test loop when they are expensive or unstable.
- Such exceptions do not remove the need for a periodic or manual real-provider validation path.
- Any exception should preserve the production contract shape so that mocked behavior does not drift from the real dependency.

## Test Hygiene

- Keep fixtures small, stable, versioned, and easy to inspect.
- Keep test commands directly runnable in the current repository layout.
- Avoid hidden environment assumptions such as implicit module paths or machine-specific files.
- Keep generated outputs in owned locations so they can be inspected and cleaned consistently.
