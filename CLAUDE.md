# siri-assistants

Voice assistants ("Appelle Gemini" / "Appelle Gemma") over SSH on macOS and `pc-benjamin`. Full architecture & operations: [`README.md`](README.md). Detailed layout & security invariants: [`AGENTS.md`](AGENTS.md).

## Engineering Standards (Mandatory)

1. **Typed domain models — no ad-hoc complex JSON dicts**:
   - Prefer stdlib `@dataclass` models with explicit `.to_dict()` serialization for structured payloads, pending actions, and configurations rather than assembling nested untyped dicts across procedural functions.
2. **Modular, readable code (stdlib only, `python3 -I`)**:
   - Keep functions short and single-responsibility (~30–100 lines); maintain the acyclic DAG in `tools_lib/` (`config` ← `paths` ← `pending` ← `files`).
   - Keep `google-bridge.py` self-contained (stdlib + `spoken_dates.py` only, because `home-server/server/google-bridge.sh` fetches only those two files).
   - Zero third-party Python dependencies; all scripts must run cleanly under `/usr/bin/python3 -I`.
3. **100% English technical code**:
   - All code identifiers, filenames, comments, docstrings, tests, documentation, and commit messages in **English**.
   - Spoken French prompts, Siri responses, tool descriptions, and the frozen French bridge HTTP action verbs/arguments (`mails`, `repondre`, `rdv`, etc.) remain in **French**.
4. **Mandatory offline tests & up-to-date docs**:
   - Every new feature, module, or bug fix MUST include offline `python3 -I` unit tests in `tests/test_*.py` (no network, no real Google tokens).
   - Update `README.md`, `CLAUDE.md`, and `AGENTS.md` in the same change whenever scripts, providers, interfaces, or tests change.
5. **Required checks before every commit**:
   ```sh
   ruff check . && ruff format --check .
   python3 -m py_compile tools.py tools_lib/*.py google-bridge.py spoken_dates.py build-shortcuts.py add-task google recap tests/test_*.py
   zsh -n ask-gemini ask-local ask-ssh
   python3 -I tests/test_google_bridge.py
   python3 -I tests/test_tools.py
   python3 -I tests/test_spoken_dates.py
   ```
6. **Never push directly to `main`** without Benjamin's explicit confirmation (a green push to `main` auto-promotes `production` and deploys to `pc-benjamin`).
