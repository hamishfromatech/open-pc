# Open-PC × CUA Integration Plan

> **Status:** Proposed · **Created:** 2026-09-26 · **Executor:** intended to be implemented by an LLM agent
> **Reference repo:** [hamishfromatech/cua](https://github.com/hamishfromatech/cua) (fork of trycua/cua) — a local clone was made at `/tmp/cua-review` (re-clone with `git clone --depth 1 https://github.com/hamishfromatech/cua /tmp/cua-review` if gone).
> **Upstream docs:** https://cua.ai/docs

---

## Table of Contents

1. [Context & Motivation](#1-context--motivation)
2. [Current Architecture (as-is)](#2-current-architecture-as-is)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Licensing Constraints (READ FIRST)](#4-licensing-constraints-read-first)
5. [Phase 1 — cua-driver in the image: semantic desktop control](#phase-1)
6. [Phase 2 — cua-bench evaluation harness](#phase-2)
7. [Phase 3 — Trajectory recording (computer-history)](#phase-3)
8. [Phase 4 — SoM visual grounding container](#phase-4)
9. [Phase 5 — CUA `computer` SDK compatibility layer](#phase-5)
10. [Phase 6 — Multi-arch image (arm64)](#phase-6)
11. [Execution Notes for the Implementing Agent](#11-execution-notes-for-the-implementing-agent)
12. [Definition of Done (whole plan)](#12-definition-of-done)

---

## 1. Context & Motivation

Open-PC gives AI agents a complete Linux desktop in a container (XFCE on X11 + TigerVNC +
noVNC), controlled through a FastAPI `agent_server.py` (pixel-space screenshot/mouse/keyboard),
an MCP server (`openpc_mcp.py`), a dashboard, an SDK, and a CLI.

The CUA (Computer-Use Agents) project provides several production-grade, MIT-licensed
components that Open-PC can adopt to close its biggest gaps:

| Open-PC gap today | CUA component that fixes it | License |
|---|---|---|
| Agents control the desktop only by **pixel coordinates** (click x,y after looking at a screenshot) — fragile, slow, token-hungry | `cua-driver` — Rust driver exposing **AT-SPI accessibility trees** on Linux X11 (our exact stack: XFCE + Xvfb + TigerVNC). Click "the Save button" by element, not by pixel | MIT (core) |
| **No evaluation story** — we cannot say whether an agent succeeds at a task, or detect regressions | `cua-bench` — gym-style task framework (`make/reset/step/evaluate`), verifiable tasks, worker protocol | MIT |
| **No session record** — agent sessions vanish; no replay, audit, or training data | cua-driver "computer-history" event system (JSON-schema'd action events) + ffmpeg trajectory video | MIT |
| Element finding is template-matching only (`/mouse/locate`); no visual grounding | `cua-som` — YOLO icon detection + OCR → labeled Set-of-Mark bounding boxes. CUDA-capable (we now ship GPU support) | **AGPL-3.0** ⚠️ |
| CUA-ecosystem agents can't talk to Open-PC | Their `computer` Python SDK interface, reimplemented as a client of our REST API | MIT |
| Image is amd64-only | Their `xfce-cua` Dockerfile builds `linux/amd64` + `linux/arm64` | MIT |
| For A-Coder Cloud (`docs/cloud/`): pool-of-desktops lifecycle design | `cua-fleet` / `cua-sandbox` claim/return architecture (reference reading, not code to import) | MIT |

**Upstream compatibility note:** Open-PC was historically compared to CUA's own stack. CUA's
`libs/xfce-cua` image is Debian + XFCE + X11 VNC + cua-driver — nearly identical to ours. This
plan makes Open-PC *the* image that CUA's driver and bench tooling target, instead of competing.

---

## 2. Current Architecture (as-is)

Facts the implementing agent must know before touching anything. Verify these by reading the
files — do not assume.

### Key files in Open-PC (this repo)

| Path | Role |
|---|---|
| `docker/Dockerfile` | Builds the desktop container: XFCE4, TigerVNC (`VNC_PORT=5901`, `VNC_RESOLUTION=1920x1080`), noVNC, Flask etc. Entrypoint: `docker/startup.sh` → `docker/xstartup` |
| `docker/agent_server.py` | FastAPI REST API + WebSocket server. Endpoints: `/health`, `/capabilities`, `/screenshot` (+`/base64`, `/base64/compressed`, `/region`), `/mouse/*` (move, click, double-click, right-click, scroll, drag, position, locate, locate-base64), `/keyboard/*`, `/screen`, `/stream` (MJPEG), `/batch`, window management, `/apps/run`. Auth: bearer token (`require_token`). Rate-limited. |
| `docker/backends.py`, `docker/command_runner.py`, `docker/io_utils.py`, `docker/sanitization.py`, `docker/health_check.py` | Support modules for agent_server (shipped in the Docker image as of commit `b5125d6`) |
| `docker/requirements.txt` | fastapi 0.109.0, uvicorn 0.27.0, pyautogui 0.9.54, Pillow, mss, python-xlib, opencv-python-headless, pytesseract, pydantic 2.5.0 |
| `mcp-server/openpc_mcp.py` | MCP server (streamable-http, stateless CORS — as of commit `49ecd0a`/`913470c`). Tools: `take_screenshot`, `take_screenshot_full`, `get_screen_size`, `move_mouse`, `click`, `double_click`, `right_click`, `scroll`, `drag`, `type_text`, `press_key`, `press_hotkey`, `list_windows`, `focus_window`, `close_window`, `maximize_window`, `minimize_window`, `launch_application`, `open_url`, `run_command`, `perform_ocr`, `wait_seconds`, `get_desktop_status`. It is a thin client — every tool calls the agent_server REST API over HTTP (`agent_server_client` class, base `BASE_URL`, token `OPENPC_PASSWORD`). |
| `docker-compose.yml` / `docker-compose.gpu.yml` | Service definitions; GPU overlay adds NVIDIA CUDA 12.6 + PyTorch passthrough (commits `0afaf10`, `ab5f6de`) |
| `openpc-sdk/` | Python + TypeScript SDK wrapping the REST API |
| `openpc.py` | noun-verb CLI (start/stop/status/logs/screenshot/exec/doctor/...) |
| `dashboard/` | Web UI (port 8092) |
| `docs/cloud/README.md` | A-Coder Cloud (Sovereign Edition) roadmap — uncommitted work at plan time |

### Key components in the CUA repo (`/tmp/cua-review`)

| Path | What it is |
|---|---|
| `libs/cua-driver/` | Rust binary + Python/TS SDK + MCP mode. Linux X11 support via AT-SPI (`x11_atspi` delivery path), Wayland via helpers. `docs/action-support.md` lists per-platform action matrix. Python package name: `cua-driver` (see `libs/cua-driver/python/pyproject.toml`). Runs as a daemon (`cua-driver serve`) exposing an HTTP/WS + MCP interface. `--dangerously-bypass-approvals` disables interactive consent (appropriate inside a headless agent desktop). |
| `libs/cua-bench/` | Task framework. `cua_bench` Python package. Tasks are directories with a `main.py` registering `@cb.tasks_config` and a `cb.Task(...)` with `computer={"provider": ..., "setup_config": {...}}`; example tasks in `libs/cua-bench/example_tasks/` (`test_click_env`, `basic_gui_env`, `advanced_gui_env`, `2048_env`, ...). Gym interface: `make()/reset()/step()/evaluate()`. Worker protocol: HTTP `/reset`, `/step` endpoints (`test_worker_server.py`). |
| `libs/cua-driver/docs/computer-history-event-v0.schema.json` | JSON schema for trajectory event records |
| `libs/python/som/` | Set-of-Mark: YOLO icon detection + EasyOCR, auto device MPS→CUDA→CPU. **AGPL-3.0** |
| `libs/python/computer/` | The `cua-computer` client SDK (the interface agents use: `computer.screen.*`, `computer.mouse.*`, ...) |
| `libs/python/computer-server/` | Their in-sandbox runtime (`server.py`, `handlers/{linux,vnc,cua_driver,...}.py`). Study `handlers/vnc.py` — it's how *they* drive a VNC/X11 desktop; useful reference for our Xvfb session |
| `libs/xfce-cua/` | Reference Dockerfile for multi-arch XFCE image with cua-driver preinstalled |

---

## 3. Goals & Non-Goals

### Goals
1. G1: Agents can click/type by **UI element** (accessibility tree), with pixel actions as fallback.
2. G2: Deterministic **evaluation** of agents against Open-PC tasks with pass/fail scoring, runnable locally and in CI.
3. G3: Every agent session produces a **replayable structured trajectory** (JSON events + optional video).
4. G4: Optional GPU-accelerated **visual grounding** endpoint (labeled screenshot elements).
5. G5: **Compatibility** with the existing CUA agent ecosystem via the `computer` SDK interface.
6. G6: **arm64** images.

### Non-Goals
- Replacing pyautogui/mss pixel control — it stays as the fallback layer and is still the only path for apps without AT-SPI exposure.
- Importing CUA code wholesale into this repo. We consume `cua-driver` as an installed package/binary; we *reimplement* thin adapters.
- Modifying the CUA fork (except, optionally, upstreaming an Open-PC bench environment later — out of scope for v1).
- Any managed/cloud service work (A-Coder Cloud is a separate plan; this plan only informs it).

### Success metrics
- An MCP client can complete "open Files, create folder 'test', verify it exists" using only semantic (element-based) actions.
- `pytest` in the bench harness reports pass/fail per task per model; a task runs green against the Open-PC container on a clean `docker compose up`.
- A 60-second agent session yields a valid trajectory JSON file that replays actions in order when re-executed.

---

## 4. Licensing Constraints (READ FIRST)

| Component | License | Rule for us |
|---|---|---|
| `cua-driver` (default, no model artifacts) | **MIT** | May vendor/install/embed freely. Keep the MIT notice in our `NOTICE`/docs. |
| `cua-driver` optional OmniParser extension | **NOT MIT** | **Do not enable or redistribute.** Never add its model artifacts to the image. |
| `cua-bench`, `cua-computer`, `cua-sandbox` | **MIT** | Free to use; keep notices. |
| `cua-som` | **AGPL-3.0** | Must live in a **separate container/service**, never imported by our MIT code or linked at the library level. Access over HTTP only. If we ever distribute Open-PC including it, the combined work obligations of AGPL apply to *that component only* — keep it cleanly separable and optional (env-gated, off by default is not sufficient alone — separate image is the requirement). |
| CUA repo top-level `LICENSE.md` | MIT (Cua AI, Inc., 2025) | Applies per-component as tabled above; check each component's own `LICENSE`/`pyproject.toml` before vendoring anything new. |

Add a `NOTICE` file at repo root listing embedded upstream components and licenses as part of Phase 1.

---

<a name="phase-1"></a>
## Phase 1 — cua-driver in the image: semantic desktop control (G1)

> **Highest value.** Do this phase first and completely before others.

### 1.1 Spike: prove AT-SPI works inside our container

Inside the existing container session (Xvfb + XFCE + TigerVNC on `:1`), install and start the
driver and confirm it can enumerate UI elements of an XFCE app.

Steps:
1. `docker compose up -d`, then `docker exec -u <desktop-user> open-pc-desktop bash`.
2. Install: `pip install cua-driver` (or download the prebuilt Rust binary via their install
   script — prefer pip for image reproducibility; pin the version in `docker/requirements.txt`).
3. Install AT-SPI runtime deps if missing: `at-spi2-core`, `at-spi2-atk`, `gir1.2-atspi-2.0`,
   `libatk-adaptor`, `atkbridge` (exact set varies on Debian — check `libs/xfce-cua/Dockerfile`
   and `libs/cua-driver/docs/linux-desktop-validation.md` in the CUA clone for the known-good set).
4. Ensure the accessibility bus exists: set `NO_AT_BRIDGE=0`, ensure `dbus-x11` session bus is
   running for the desktop user (our `xstartup` already starts dbus — verify `dbus-launch` wraps
   the session), and `GTK_MODULES=gail:atk-bridge` where needed.
5. Start driver: `cua-driver serve --dangerously-bypass-approvals` with `DISPLAY=:1`, run in background.
6. Verify: launch `xfce4-terminal`, query the driver (via its Python SDK from another exec shell)
   for the element tree; confirm buttons/menus appear with roles and names.

**Exit criteria:** element tree of two different XFCE apps (terminal + file manager) is returned
with stable element IDs.

**If AT-SPI does not work over our Xvfb session:** document the exact failure in this file under
"Phase 1 spike findings", and evaluate switching our X startup to match `libs/xfce-cua`'s known-good
X11 setup (their `Dockerfile` + `src/`). Do not proceed to 1.2 until the spike passes.

### 1.2 Image changes

In `docker/Dockerfile`:
- Add `cua-driver` (pinned version) to pip installs; add AT-SPI system deps from the spike.
- Copy a new `docker/entrypoint.d/60-cua-driver.sh` (create `entrypoint.d/` if the pattern doesn't
  exist — otherwise append to `docker/startup.sh` in the same style as existing service startup)
  that starts `cua-driver serve --dangerously-bypass-approvals` in the background **after** the X
  session and dbus are up, retries until the driver's health port answers (max 30s), and is a
  no-op when env `OPENPC_ENABLE_CUA_DRIVER != true` (keep the image's default behavior unchanged).
- Default `OPENPC_ENABLE_CUA_DRIVER=true` in `.env.example` with a comment; document in README.

### 1.3 REST surface: `/semantic/*` routes in `agent_server.py`

Add a `docker/semantic_backend.py` module (follow the pattern of `backends.py`) that:
- Holds a lazy client to the local driver (host/port from env `CUA_DRIVER_URL`, default
  `http://127.0.0.1:<driver port>` — read the actual port from the driver docs/source; make it env-overridable).
- Normalizes driver responses into a small DTO set (pydantic, matching existing request-model style):
  - `ElementInfo { id, role, name, app, bbox?, actions[], children_count }`
  - `ElementTree { app, window_title, elements[] (flattened, with parent/child refs) }`
  - `ActionResult { ok, detail }`
- Implements graceful degradation: every call has a `timeout` (default 5s); on driver
  unavailable → raise `_actionable_error(...)` with message telling the caller to fall back to
  pixel endpoints (`/mouse/*`, `/keyboard/*`).

New routes in `agent_server.py` (all behind existing `require_token`, rate limits, and sanitization
practices — mirror how `/mouse/click` validates input):

| Route | Method | Body / Query | Behavior |
|---|---|---|---|
| `/semantic/tree` | GET | `?app=&window=` (optional filters) | Flattened AT-SPI element tree for current desktop or one app |
| `/semantic/element/{id}` | GET | — | Single element detail incl. actionable verbs |
| `/semantic/click` | POST | `{element_id, action?}` | Invoke element default action (or named action) via driver |
| `/semantic/set-value` | POST | `{element_id, value}` | Set text/value on editable elements |
| `/semantic/read` | GET | `?element_id=&max_depth=` | Text content of element subtree |
| `/semantic/status` | GET | — | Driver version, reachable, element counts (for `/capabilities` & dashboard) |

- Extend the existing `/capabilities` response with a `semantic` object
  (`{"enabled": bool, "driver_version": str|null}`) so SDKs can feature-detect. **Bump the
  capabilities version field if one exists** (check `capabilities()` at ~line 337).
- `/batch` should accept semantic ops too (same dispatch table style as existing ops) so agents
  can mix screenshot → find element → click in one round-trip.

### 1.4 MCP tools in `mcp-server/openpc_mcp.py`

Add tools, same thin-client style as existing ones (each calls agent_server over HTTP):

| Tool | Maps to | Docstring guidance for the LLM agent |
|---|---|---|
| `get_ui_tree(app: str = "", window: str = "")` | `/semantic/tree` | "Prefer this over screenshots when you need to find a button/field. Returns roles+names+ids." |
| `click_element(element_id: str)` | `/semantic/click` | "Click a UI element by ID from get_ui_tree." |
| `set_element_value(element_id: str, value: str)` | `/semantic/set-value` | "Type into a field by element ID (more reliable than type_text)." |
| `read_element(element_id: str = "", max_depth: int = 5)` | `/semantic/read` | "Read text content of an element or whole window." |
| `semantic_status()` | `/semantic/status` | "Check whether semantic control is available." |

- Each tool's docstring should explicitly tell the calling LLM when to prefer semantic over pixel
  (that's what changes agent behavior).
- Update `mcp_config.example.json` if it enumerates tools (check — it currently doesn't list tools;
  if so, no change).

### 1.5 SDK + CLI

- `openpc-sdk/python` and `openpc-sdk/typescript`: add typed wrappers for the six routes
  (`semantic.tree()`, `semantic.click(id)`, ...). Follow existing module structure.
- `openpc.py`: add `openpc.py ui-tree [--app APP]` and `openpc.py semantic` (status) commands —
  useful for humans and for the implementing agent's own verification.

### 1.6 Tests

- `tests/test_semantic_backend.py` (pytest, mirrors existing tests dir conventions):
  - Unit: DTO normalization with a recorded driver-response fixture (capture one during the spike
    and commit it as `tests/fixtures/cua_driver_tree.json`).
  - Unit: driver-unavailable → `_actionable_error` with fallback hint.
  - Unit: `/capabilities` includes `semantic` block.
- Mark integration tests (real container) with the same skip-if-no-docker pattern existing tests use.

**Phase 1 acceptance:** with a fresh `docker compose up -d` and `OPENPC_ENABLE_CUA_DRIVER=true`,
an MCP client lists windows, gets a UI tree for `xfce4-files` (or thunar — check which file manager
the image ships), clicks an element by ID, and the action is reflected on the noVNC screen. All
existing pixel endpoints still pass their tests. `NOTICE` file added.

---

<a name="phase-2"></a>
## Phase 2 — cua-bench evaluation harness (G2)

> Requires Phase 1 complete (bench tasks will use semantic + pixel APIs).

### 2.1 Create `bench/` top-level directory

```
bench/
  README.md               # how to run evals
  tasks/
    openpc_click_env/     # first task: simple, deterministic
      main.py
    openpc_files_task/    # file-manager task
      main.py
    openpc_browser_task/  # open URL, verify load
      main.py
  runner.py               # orchestration: start container → run task → report
  report.py               # JSON + markdown result output
```

### 2.2 Task format

Follow `libs/cua-bench/example_tasks/test_click_env/main.py` exactly (read it from the CUA clone):
`@cb.tasks_config(split="test")`, a `cb.Task(...)` per variant, `@cb.setup`/teardown hooks, and a
verifiable `evaluate()` (e.g., for the files task: `assert (Path.home()/"test-folder").exists()`
run inside the container).

For v1, use `provider: "native"` with `os_type: "linux"` and have the task's setup/evaluate step
exec into the running Open-PC container (`docker exec` or REST `/apps/run`). Document this
deviation from CUA's own providers clearly in `bench/README.md` — Open-PC *is* the environment;
we do not need bench to provision a VM.

Add `cua-bench` as a **dev dependency** (extras group `bench` in `pyproject.toml`), not a runtime dep.

### 2.3 Runner

`bench/runner.py`:
1. `docker compose up -d --wait` (or reuse running stack with `--reuse` flag).
2. For each selected task: reset desktop state (restart container, or close all windows via
   `wmctrl -c` loop — pick based on what the spike shows is most reliable), run task steps
   against the agent under test, call `evaluate()`.
3. "Agent under test" is pluggable: v1 ships one reference agent that drives the desktop via the
   MCP tools with any OpenAI-compatible chat endpoint (env: `OPENPC_EVAL_BASE_URL`,
   `OPENPC_EVAL_MODEL`, `OPENPC_EVAL_API_KEY`). Keep it <300 lines; it's an example, not a framework.
4. Output `bench/results/<timestamp>/<task>.json` + a combined `summary.md` (pass rate, steps, duration).

### 2.4 CI

Add `.github/workflows/bench.yml` (manual-dispatch + `workflow_dispatch` on label `bench`):
matrix over one small model (e.g. a cheap OpenAI-compatible model) × the 3 tasks; upload
`bench/results` as artifacts. Keep it opt-in — do not run on every push (cost).

**Phase 2 acceptance:** `python bench/runner.py --task openpc_click_env --model <x>` runs against
a live container and prints a pass/fail summary; results JSON committed as a fixture for the
`report.py` unit test.

---

<a name="phase-3"></a>
## Phase 3 — Trajectory recording (G3)

### 3.1 Event log in `agent_server.py`

- New module `docker/trajectory.py`. A `TrajectoryRecorder` singleton, env-gated
  (`OPENPC_RECORD_TRAJECTORIES`, default false; `OPENPC_TRAJECTORY_DIR`, default `/data/trajectories`).
- Every mutating route (`/mouse/*`, `/keyboard/*`, `/semantic/*`, `/batch` items, window routes,
  `/apps/run`) emits a `step` event through a middleware/hook **after** the action completes,
  containing: `ts`, `action_type`, `params` (sanitized — reuse `sanitization.py`; redact token),
  `result_ok`, `duration_ms`, and an optional `screenshot_ref` (filename of a captured frame —
  capture at low quality to keep size sane, only when `OPENPC_TRAJECTORY_SCREENSHOTS=true`).
- File format: follow `libs/cua-driver/docs/computer-history-event-v0.schema.json` from the CUA
  clone as closely as practical — one JSONL file per session
  (`<ts>-<session_id>.events.jsonl`), header event with schema id, screen size, image version.
  Reuse their schema where it matches; where it doesn't, add a `openpc/` namespaced field, and
  document deviations in a header `"openpc_extensions"` key.
- Session id: minted at server lifespan start (see existing `lifespan` at ~line 214); each WS
  client may carry its own `X-Session-Id` header to segment events (optional).

### 3.2 Replay utility

- `openpc.py trajectory <file>` subcommand: prints a human-readable summary of the JSONL
  (counts by action type, duration, errors).
- `openpc.py trajectory --replay <file>`: re-executes the actions in order against the REST API
  (pixel + semantic routes both). This is the core of "replayable" — and doubles as a debugging tool.

### 3.3 Video (optional, env-gated)

If `ffmpeg` is easy to add to the image (check `libs/xfce-cua` — they do exactly this for
trajectory video): record `/stream` MJPEG into an mp4 per session. Skip if it complicates the
Dockerfile beyond a single `apt-get install ffmpeg` + one thread in `trajectory.py`.

### 3.4 Tests

- Unit: middleware records an event for a mock route; sanitization redacts tokens; JSONL is valid
  per our documented schema.
- Unit: replay of a 5-event fixture executes the expected HTTP calls (mock client).

**Phase 3 acceptance:** `OPENPC_RECORD_TRAJECTORIES=true docker compose up -d`, drive the desktop
via MCP for a minute, find `*.events.jsonl` in the mounted volume, `openpc.py trajectory --replay`
repeats the session.

---

<a name="phase-4"></a>
## Phase 4 — SoM visual grounding container (G4) ⚠️ AGPL

### 4.1 Separate service, separate image

- New `docker/grounding/Dockerfile` (NOT added to the main desktop image): installs
  `cua-som` from the CUA clone (`libs/python/som`) or upstream. Pin versions.
- New `docker-compose.grounding.yml` overlay: service `open-pc-grounding`, env
  `SOM_DEVICE=auto`, healthcheck, no external ports by default (bind on the compose network only).
  GPU passthrough composes with the existing `docker-compose.gpu.yml` overlay.
- **Off by default.** README section explains the AGPL implication and when to enable.

### 4.2 API

FastAPI wrapper (single file) exposing:
- `POST /ground` — body: `{"image_b64": "...", "prompt": "optional text"}` →
  `{"elements": [{"id": n, "type": "icon"|"text", "bbox": [x,y,w,h], "label": ...}]}`
- The grounding service fetches screenshots from the desktop container itself (`DESKTOP_URL`
  env) so the caller can just `POST /ground/detect`.

### 4.3 Integration (thin, license-safe)

- `agent_server.py` gains one route: `POST /ground` that **proxies** to the grounding service if
  `GROUNDING_URL` is set, else 404 with an actionable message ("start the grounding service: docker
  compose -f docker-compose.yml -f docker-compose.grounding.yml up -d"). Proxying-by-HTTP is the
  license-safe pattern; no som code is imported.
- MCP tool: `find_elements(prompt: str = "")` → labeled elements with bboxes, so an LLM can say
  "click element 7" → we translate bbox center → existing `/mouse/click`.
- This composes with `/screenshot/base64/compressed`: ground the compressed image, act on full-res
  coordinates (document the rescale math explicitly — bboxes are in compressed-image space).

**Phase 4 acceptance:** with grounding service up, `find_elements()` returns labeled boxes on a
screenshot of the desktop, and clicking element N lands on the right UI element.

---

<a name="phase-5"></a>
## Phase 5 — CUA `computer` SDK compatibility layer (G5)

- New package `openpc-sdk/python/cua_compat/` (inside the existing SDK, no new repo) implementing
  the subset of the `cua-computer` interface our REST API can satisfy:
  `computer.screen.size()/screenshot()`, `computer.mouse.move/click/double_click/scroll/drag`,
  `computer.keyboard.type/press/hotkey`, window listing, `computer.cli.execute_command`
  (→ `/apps/run`). Map to `cua_compat` on `list_windows`, etc. Read
  `libs/python/computer/cuacomputer/` from the CUA clone for the exact method signatures —
  mirror them, don't invent.
- Ship it as an extras group: `pip install openpc-sdk[cua]`.
- Tests: mock-transport tests asserting our REST calls match CUA client expectations
  (mock at the HTTP layer like existing SDK tests do).

**Phase 5 acceptance:** a script written against `cua_computer.Computer(provider="openpc", ...)` runs
unmodified against a live container.

---

<a name="phase-6"></a>
## Phase 6 — Multi-arch image (G6)

- Mirror `libs/xfce-cua/Dockerfile` techniques: avoid amd64-only packages, use
  `--platform=$BUILDPLATFORM` build stages where tooling requires.
- GitHub Actions workflow `release-multiarch.yml`: `docker buildx build --platform linux/amd64,linux/arm64`
  pushing to GHCR. arm64 caveats: verify pyautogui/python-xlib deps, and that cua-driver publishes
  arm64 Linux binaries (check their releases; if not, make the driver install arch-conditional and
  let arm64 run pixel-only — semantic features degrade gracefully by design).
- Add `docs/` note documenting the arm64 support level (pixel control guaranteed; semantic
  control depends on driver arm64 availability).

**Phase 6 acceptance:** `docker buildx build --platform linux/arm64 docker/` succeeds locally
(via QEMU) and the arm64 container passes the smoke test (`/health`, screenshot, click).

---

## 11. Execution Notes for the Implementing Agent

### Order & dependencies
```
Phase 1 (semantic) ──► Phase 2 (bench) ──► Phase 3 (trajectories)
                  └──► Phase 4 (grounding, independent of 2/3)
Phase 5 (compat SDK) — any time after Phase 1
Phase 6 (multiarch) — last
```
Phases 2–4 each build on Phase 1's routes; Phase 4 is otherwise independent of 2/3.

### Repo conventions to respect
- Commit style: conventional commits (`feat(api): ...`, `fix(docker): ...`, `docs(readme): ...`) —
  see `git log` for tone; each phase should be 1–4 logical commits, not one mega-commit.
- Error handling: use the existing `_actionable_error` helper (`agent_server.py` ~line 76) — errors
  must tell the caller exactly how to recover.
- Every new route: auth (`require_token`), rate limit, pydantic request model, docstring. Match
  existing route style exactly.
- README updates accompany user-visible features (see how the GPU feature was documented in
  commit `ab5f6de`).
- Don't touch `docs/cloud/` or the uncommitted README changes — they belong to a separate workstream.
- Uncommitted work may exist in the tree (README.md, docs/README.md edits as of 2026-09-26).
  Check `git status` first and don't include unrelated changes in your commits.

### Environment / verification loop
- Iterate with `docker compose up -d --build` + `curl -H "Authorization: Bearer $OPENPC_PASSWORD" localhost:8090/...`
  (check the actual port/认证 header style in `agent_server.py` — bearer token `require_token`).
- The implementing agent (you) can verify element trees via `docker exec` + the driver's Python SDK.
- Run `pytest tests/` before every commit; the existing suite must stay green.

### Known unknowns (resolve during spikes, document answers here)
- Exact cua-driver serve port + API shape on Linux → fill in after Phase 1 spike: `______`
- Whether dbus session in `xstartup` is sufficient for AT-SPI, or needs `dbus-launch`/system bus tweaks: `______`
- arm64 availability of cua-driver binaries: `______`
- Which file manager ships in the image (thunar vs nautilus) for Phase 1/2 tasks: `______`

## 12. Definition of Done (whole plan)

- [ ] Phase 1–6 merged, each with tests and README/`bench/README.md`/`NOTICE` documentation
- [ ] `docker compose up -d` on a clean host → all existing + new smoke checks pass
- [ ] Bench run produces a summary.md for the 3 starter tasks
- [ ] A recorded trajectory replays successfully
- [ ] `NOTICE` and licensing table in this doc match what actually ships
- [ ] No AGPL code linked into MIT components (audit: `grep -r "import som"` and compose config review)
