# A-Coder Cloud — Sovereign Edition

> **Status:** Planned (v0 not started). This document is the agreed architecture and roadmap.
> **Date:** 2026-09-12
> **Owners:** The A-Tech Corporation PTY LTD

---

## Summary

A-Coder Cloud turns Open-PC's architecture into a fleet of **always-on a-coder-cli agents**: self-hosted workspace containers that keep working whether the user's machine is on or off. When the user returns to A-Coder IDE, CLI, or Desktop, the work is waiting — a git branch with WIP commits, a full report, and the live session itself, resumable where the cloud left off.

**The Sovereign Edition (this plan) is the reference implementation.** The Hosted Edition (multi-tenant, on A-Tech infrastructure, Amaara-billed) is the same control plane with tenancy and billing added later — build once, deploy twice.

One sentence: **git is the sync API, the session is the source of truth, the branch is the deliverable.**

---

## Relationship to Open-PC

- **Open-PC stays Open-PC.** It remains its own open-source project — "Give AI its own computer" — and its own entry in The A-Tech Corporation software lineup. It is not renamed.
- **A-Coder Cloud is a control plane built on Open-PC's foundations:** Docker Compose orchestration, FastAPI agent server, WebSocket + REST + token auth (`REST_AUTH_TOKEN`), health checks with auto-restart, resource limits, and the React dashboard.
- **Two worker runtimes:**
  - *Workspace worker* (default): headless container — repo clone, toolchain, `a-coder-cli` running in RPC mode. This is where 90% of coding tasks live.
  - *Desktop worker* (optional, later): the full Open-PC desktop container, for tasks that need eyes — running the app under test, browser verification, screenshots into the report. This is the differentiator: most cloud agents are headless-only.
- **Editions:**
  - **Sovereign Edition** — self-hosted on hardware the user owns (home server, office box, Infra Store machine). $0. Open source. This plan.
  - **Hosted Edition** — multi-tenant on A-Tech infrastructure, Australian region, billed like Amaara Cloud (request-credit or bundled with A-Coder Pro). Derived from Sovereign, not built separately.

---

## Product principles

1. **The branch is the deliverable.** Agents never push to main. Work lands on `ac-cloud/<task-id>`; merging is always the user's call.
2. **The session is the source of truth.** The user gets more than a diff — the same session JSONL they can open locally and continue.
3. **Checkpoint, restart, resume.** "Never stop" means persistence, not idle token burn. Budgets, sleep-on-idle, wake-on-dispatch.
4. **$0 and sovereign.** Runs on the user's own hardware, data never leaves their building.
5. **Reports over presence.** The user reads a report, not a log.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    A-Coder Cloud (Sovereign Edition)                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────────┐   ┌───────────────────┐   ┌──────────────────┐  │
│  │  Dashboard   │   │  Control plane    │   │  Client (IDE /   │  │
│  │  (React,     │──▶│  (orchestrator)   │◀──│  CLI / Desktop)  │  │
│  │  extends     │   │  FastAPI          │   │  a-coder cloud … │  │
│  │  Open-PC's)  │   │  • task queue     │   └──────────────────┘  │
│  └──────────────┘   │  • worker registry│                         │
│                     │  • budgets        │                         │
│                     │  • WS event fanout│                         │
│                     └────────┬──────────┘                         │
│                              │                                     │
│              ┌───────────────┼───────────────┐                     │
│              ▼               ▼               ▼                     │
│     ┌──────────────┐ ┌──────────────┐ ┌────────────────┐           │
│     │ Workspace    │ │ Workspace    │ │ Desktop worker │           │
│     │ worker #1    │ │ worker #N    │ │ (optional)     │           │
│     │ repo+toolchain│ │ ...         │ │ Open-PC GUI    │           │
│     │ a-coder RPC  │ │             │ │ visual verify  │           │
│     └──────┬───────┘ └──────┬──────┘ └───────┬────────┘           │
│            │                │                │                     │
│            ▼                ▼                ▼                     │
│     ┌─────────────────────────────────────────────────┐           │
│     │  Git sync + report builder                      │           │
│     │  WIP commits → ac-cloud/<task-id> → report.md   │           │
│     └─────────────────────────────────────────────────┘           │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Description | Reuses from Open-PC |
|-----------|-------------|---------------------|
| **Control plane** | FastAPI orchestrator: task queue, worker registry, budgets, event fanout | Agent server patterns, token auth, WebSocket, health checks |
| **Workspace worker** | Container: repo clone + toolchain + `a-coder-cli` in RPC mode, driven by a supervisor | Compose service model, resource limits, auto-restart |
| **Desktop worker** | Optional GUI container for visual verification | The entire Open-PC desktop stack |
| **Git sync service** | WIP commits, branch management, PR creation | — (new) |
| **Report builder** | Aggregates commits, diffstat, test results, screenshots, cost, and a model-written summary into `report.md` + structured JSON | — (new) |
| **Dashboard** | Fleet view, live session stream, task history | Existing React dashboard + MJPEG/stream patterns |
| **Client integration** | `a-coder cloud …` commands; IDE/Desktop panels; session import | Existing background-agent / agents-panel UI patterns |

---

## Lifecycle: the checkpoint loop

```
spawn → provision → work ⇄ checkpoint → complete → report → sync-back
```

1. **Spawn** — user dispatches a task from CLI, IDE, Desktop, or dashboard.
2. **Provision** — control plane allocates a workspace container, clones the repo, injects scoped secrets, starts `a-coder-cli` in RPC mode with the task prompt.
3. **Work ⇄ checkpoint** — every N minutes or on tool completion, the worker pushes a WIP commit to `ac-cloud/<task-id>` and uploads the session JSONL. The dashboard streams events live.
4. **Complete** — agent finishes (or hits a budget/limit). Final commit, PR opened if the host supports it, otherwise branch + report.
5. **Report** — `report.md` at the branch tip plus structured JSON for clients.
6. **Sync-back** — on next client start: "N cloud agents finished while you were away." Review diff, import session, continue locally, or dispatch follow-ups.

**Failure paths are first-class:**
- Container death → supervisor restarts → agent resumes from last checkpoint (session + WIP commits).
- Context overflow → mid-run compaction and HTTP 413 recovery (already shipped in a-coder-cli) keep long runs alive.
- Provider outage → `retryAfterMs`-honoring backoff, then model fallback.
- Budget exhausted → agent pauses cleanly, reports state, waits for top-up.
- Agent stuck → (v2) escalate to A-Coder Tandem (Innowise human developers).

---

## Sync-back and session continuity

- **Branch per task:** `ac-cloud/<task-id>`. WIP commits are cheap and frequent; history is messy by design — squash is the user's choice at merge time.
- **Report artifacts:** `report.md` (human-readable) + `report.json` (structured: commits, files, tests, screenshots, tokens, cost) at the branch tip, and duplicated into the PR description.
- **Session continuity:** the a-coder-cli session JSONL uploads continuously. `a-coder cloud review` fetches the branch *and* imports the session, so the user opens the same conversation locally — full transcript, tool calls, reasoning — and continues it as if they never left.
- **Non-git fallback:** out of scope for v0. v1 may add tarball export for non-git directories.

---

## Client surface

### v0 CLI (the whole v0 UX)

```bash
a-coder cloud spawn <repo> "Fix the flaky auth tests and add regression coverage"
a-coder cloud status              # fleet overview: running / done / stuck
a-coder cloud review <task-id>    # fetch branch + import session + open report
```

### v1+ clients

- **Dashboard panels:** fleet grid, live event stream per agent, task history (extends Open-PC dashboard).
- **IDE/Desktop panels:** "cloud agents" section reusing the background-agent bar / agents-panel patterns from the TUI.
- **Live attach:** watch an agent work in real time (event stream; MJPEG for desktop workers).

---

## Security model

- **WIP-branch-only by default.** No pushes to main; PR creation requires explicit repo policy.
- **Scoped secrets.** Per-task injection via the control plane; never baked into images; never written to the repo; never synced back.
- **Approval gates.** Destructive commands (force-push, delete, publish, infra changes) gate on the a-coder-cli trust system; cloud policy can tighten but never loosen local trust.
- **Isolation.** One container per task; no host mounts; network egress limited to the git remote, model provider, and package registries.
- **Auth.** Token auth on every API (`REST_AUTH_TOKEN` pattern carried over).
- **Blast radius.** Resource limits (CPU/mem/time) per worker; runaway agents are killed and reported, not paged about.

---

## Hard problems and mitigations

| Problem | Reality | Mitigation |
|---------|---------|------------|
| **Environment fidelity** | The user's laptop has secrets, running services, databases. Every cloud agent struggles here. | v0: standard git repos + per-language base images. v1: `devcontainer.json`, custom Dockerfile, setup-script support. Never pretend to solve "arbitrary laptop" on day one. |
| **Secrets** | Tests and builds need credentials. | Scoped injection, per-task, dashboard-managed. |
| **Verification without the user** | Agents can claim success wrongly. | Tests as the gate; desktop workers screenshot the running app for UI tasks. |
| **Cost** | Always-on fleets burn tokens. | Budgets per task, sleep-on-idle, wake-on-dispatch. |
| **Git variety** | Monorepos, LFS, private registries. | v0 scope: standard git repos; everything else is roadmap. |
| **Scale** | Multi-tenant is a different product. | Out of scope until Hosted Edition. |

---

## Milestones

### v0 — prove sync-back (the whole point) — **SHIPPED 2026-09-12**

One workspace worker. One repo. Works while the laptop is shut. Implemented as `@earendil-works/pi-cloud`
in the a-coder-cli monorepo (decided: monorepo package, see open questions).

- [x] Workspace worker: clone → `a-coder-cli` RPC agent → `ac-cloud/<task-id>` branch with WIP checkpoint commits → `report.md` (written by the agent itself) → structured report + diff summary. Docker container deferred (runs as a supervised process for now; containerization is a v1 hardening step).
- [x] Control plane: spawn/status/review API. Deviation for v0: unix-socket IPC (daemon on the same machine, secure by file permissions) instead of HTTP + token auth; HTTP/TLS arrives with the Hosted Edition.
- [x] CLI: `a-coder cloud spawn | status | review | stop | serve` (daemon auto-starts on demand).
- [x] Session continuity: session JSONL copied into the task artifacts; `cd <workspace> && a-coder --resume` reopens the exact agent session.
- [x] **Acceptance:** verified end to end — spawned a task against a scratch repo with `--model ollama-cloud/gemma4:31b`; the agent edited files, wrote its own `report.md`, checkpointed to the task branch, and `a-coder cloud review` returned commits + diffstat + usage + a resumable session.

### v1 — fleet and polish

- [ ] Parallel workers (N tasks, one container each)
- [ ] Dashboard: fleet grid, live streams, task history
- [ ] `devcontainer.json` / custom Dockerfile support
- [ ] PR creation (GitHub first)
- [ ] Desktop worker: visual verification + screenshots into reports
- [ ] IDE/Desktop cloud-agent panels
- [ ] Budgets and idle sleep

### v2 — hosted basis

- [ ] Multi-tenancy (workspaces, members, quotas)
- [ ] Amaara Cloud billing integration (request-credit / Pro hours)
- [ ] Tandem escalation hook (agent stalled → human finishes)
- [ ] Deploy the same control plane on A-Tech infrastructure (AU region)

---

## Open questions

1. ~~**v0 code location**~~ **Decided (2026-09-12): monorepo package.** The control plane ships as a new package in the a-coder-cli monorepo (e.g. `packages/cloud`), versioning and releasing with the CLI. The `a-coder cloud …` client commands live in `packages/coding-agent` as usual; the server composes Open-PC containers as its desktop-worker runtime and installs `a-coder-cli` into workspace workers.
2. **Remote write credentials:** GitHub App vs. deploy keys vs. user PAT. Lean: deploy key per workspace for v0, GitHub App for v1 PRs.
3. **Product naming inside the stack:** "A-Coder Cloud" (product) on "Open-PC" (runtime) — worker image naming TBD.
4. **Model routing:** default worker model via Amaara Cloud endpoint; fallback chain TBD.