# NOTICE — Upstream Components and Licensing

This repository intentionally consumes open-source computer-use components from the Cua AI
project (a fork of `trycua/cua`). Each component used here is listed below, its license, and
the rules that govern its use.

## Components Consumed

| Component | Source | License | Used In |
|---|---|---|---|
| `cua-driver` (driver binary + Python/TS SDK + MCP mode) | [hamishfromatech/cua](https://github.com/hamishfromatech/cua) | MIT | Phase 1 — semantic desktop control; image build |
| `cua-driver` (optional OmniParser icon detector extension) | [hamishfromatech/cua](https://github.com/hamishfromatech/cua) | **NOT MIT** | **Not used** — intentionally disabled to keep the image MIT-compliant |
| `cua-bench` (benchmark framework) | [hamishfromatech/cua](https://github.com/hamishfromatech/cua) | MIT | Phase 2 — evaluation harness |
| `cua-computer` (Python client SDK) | [hamishfromatech/cua](https://github.com/hamishfromatech/cua) | MIT | Phase 5 — compatibility layer |
| `cua-som` (Set-of-Mark grounding) | [hamishfromatech/cua](https://github.com/hamishfromatech/cua) | AGPL-3.0 | Phase 4 — gated, separate container |
| CUA repo top-level `LICENSE.md` (Cua AI, Inc.) | [hamishfromatech/cua](https://github.com/hamishfromatech/cua) | MIT | Applies per-component as tabled above |

## Licensing Rules Applied

1. **MIT-licensed components** (`cua-driver`, `cua-bench`, `cua-computer`, `cua-sandbox`):
   - May be installed, vendored, copied, and reused freely.
   - Must include the MIT license notice in every copy used.
   - May be combined with this repository's code **without additional liability** (the MIT
     terms cover "use, copy, modify, merge, publish, distribute and/or sell copies").
2. **AGPL-3.0 component** (`cua-som`):
   - **Must live in a separate container/service** and is **never imported by MIT code**,
     never linked at the library level, and never distributed together with MIT code.
   - Access is over HTTP only (the grounding service proxies to the CUA component).
   - This component is **opt-in and off by default** in Phase 4; it is never part of the
     default Open-PC runtime.
3. **Not used components** (`cua-driver` OmniParser extension): explicitly excluded from this
   repository to avoid violating the license, and documented for future reference.

## Contribution Notes

- All consumer code is written in this repository's own style (FastAPI REST, pydantic models,
  SmolVM-style error messages, existing test conventions).
- No new source code is added to the CUA repo; all CUA components are consumed as installed
  packages/binary and reimplemented as thin adapters.
- The `bench/` directory and trajectory recorders are part of this repository and are MIT-licensed
  (cua-bench); the trajectory event format follows `cua-driver/docs/computer-history-event-v0.schema.json`.

## Next Updates

- [Phase 1 (cua-driver + semantic API)](docs/plans/cua-integration-plan.md#phase-1): adds the
  semantic backend, REST routes, and MCP tools.
- [Phase 4 (SoM grounding)](docs/plans/cua-integration-plan.md#phase-4): adds the gated
  grounding container and API, with explicit AGPL handling.
- [Phase 5 (CUA SDK compat)](docs/plans/cua-integration-plan.md#phase-5): adds the `cua-computer`
  interface compatibility layer.
