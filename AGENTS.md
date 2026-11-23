# AGENTS.md — siri-assistants

Guidance for autonomous agents and contributors working in `siri-assistants`.

## Architecture & Deployment Contract

`siri-assistants` powers the voice assistants ("Appelle Gemini" / "Appelle Gemma") over SSH on both macOS and the Ubuntu home server (`pc-benjamin`).

### Layout

- `ask-ssh` — Forced SSH command (`restrict,command=`) accepting only `ask-gemini` (plus legacy `ask-haiku` alias) or `ask-local` with `--reset` or `--chat`.
- `ask-gemini`, `ask-local` — Zsh conversation scripts (`ask-haiku` is kept as a symlink to `ask-gemini` for existing shortcuts); both invoke `/usr/bin/python3 -I "${0:A:h}/tools.py"`.
- `tools.py` + `tools_lib/` — Local model tool runner and shared confirmation gateway (`--schema`, `--pending`, `--confirm`, `--cancel`).
  - `tools_lib/config.py` — Profile loading (`profile.json` / legacy `profil.json`), constants, OpenAI tool schema builder, `Refusal`, action logger.
  - `tools_lib/paths.py` — Tolerant French path matching and scope/sandbox enforcement.
  - `tools_lib/pending.py` — Pending voice-confirmation queue and Google bridge HTTP client.
  - `tools_lib/files.py` — File, search, document extraction, task, recap, and Google tool handlers.
- `google-bridge.py` + `spoken_dates.py` — Standalone local HTTP bridge (`127.0.0.1:8766`) to Google APIs and Dashboard Keep notes.
  - **Deployment constraint**: `home-server/server/google-bridge.sh` fetches **only** `google-bridge.py` and `spoken_dates.py` via HTTP from GitHub raw URLs. Keep `google-bridge.py` self-contained (relying only on the Python standard library and `spoken_dates.py`).
- `google`, `add-task`, `recap`, `build-shortcuts.py` — Helper CLIs and iOS/macOS shortcut builder.
- `tests/` — Offline test suites (`test_google_bridge.py`, `test_tools.py`, `test_recap.py`).

## Hard Rules

1. **Standard library only & `python3 -I`**: Every Python script runs in isolated mode (`-I`) with zero third-party dependencies.
   - Entrypoints (`tools.py`, `google-bridge.py`, `recap`) must explicitly prepend their real script directory to `sys.path` and avoid writing `__pycache__` when running read-only.
   - Maintain an acyclic module DAG inside `tools_lib/` (`config` ← `paths` ← `pending` ← `files`).
2. **Clean structure & typed models**:
   - Keep functions focused and concise (~30–100 lines); avoid ad-hoc deeply nested JSON dict construction when a stdlib `@dataclass` with `.to_dict()` makes the contract explicit.
   - Keep `README.md`, `CLAUDE.md`, and `AGENTS.md` updated whenever scripts, providers, interfaces, or tests change.
3. **Security invariants**:
   - Never weaken `google-bridge.py` HTTP checks (`Host`, no `Origin`, `X-Assistant: 1`).
   - Never execute destructive or external write actions without voice confirmation (`/confirmer` / `--confirm`).
   - Keep untrusted external data prefixed with the French data-not-instruction warning (`UNTRUSTED`).
   - Never expose sensitive Keep notes content or secrets in logs/stdout.
4. **Language**:
   - Technical identifiers, filenames, comments, docstrings, tests, docs, and commit messages in **English**.
   - Spoken prompts, tool descriptions/parameters, bridge action verbs/args, and user-facing answers stay in **French** (shared API contract).
5. **Mandatory offline tests**: Every new behavior or bug fix must add/update offline `python3 -I` tests in `tests/test_*.py`.
6. **Never push directly to `main`** without explicit user validation (a green push to `main` auto-promotes `production` and deploys to `pc-benjamin`).

## Required Verification Before Commit

Run the offline CI checks from the repository root:

```bash
ruff check . && ruff format --check .
python3 -m py_compile tools.py tools_lib/*.py google-bridge.py spoken_dates.py build-shortcuts.py add-task google recap tests/test_*.py
zsh -n ask-gemini ask-local ask-ssh
python3 -I tests/test_google_bridge.py
python3 -I tests/test_tools.py
python3 -I tests/test_spoken_dates.py
python3 -I tests/test_recap.py   # macOS only (uses brctl simulation)
```
