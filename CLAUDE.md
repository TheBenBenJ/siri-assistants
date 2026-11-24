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

## Readability Standards (Mandatory, same in every repository)

Full text: `docs/engineering-standards.md` of the `home-server` repository (French → English vocabulary: `docs/decisions.md` of the `dashboard` repository).

1. **Limits**: functions ≤ 60 lines (100 with a comment that says why); lines ≤ 120 characters (100 in the Dashboard's JavaScript); early returns instead of nested `if`; no dead or commented-out code; no history in comments (git and the changelog keep it).
2. **Named structures**: `@dataclass(slots=True)` or `{ key, label }` objects, never `d[0]` or a hand-built nested dict; more than 3 parameters → an options object or keyword-only signature; named constants with their unit for every threshold, delay and size.
3. **Types and docs**: annotated signatures (Python), JSDoc `@typedef` for data shapes (JavaScript); a docstring or JSDoc that says WHY on every module and shared function.
4. **Errors and output**: precise exceptions, never swallowed in silence, `raise … from error`; `logging` instead of `print` outside interactive tools.
5. **Contracts**: a key, path or protocol word read by another program (often French) is never renamed on one side only; produce it from English attributes and read it through English locals.
6. **A readability pass changes no behaviour**: characterization test first, output compared before and after, `grep -rn` every rename across the repository (tools, tests, units, installers), entry points keep their name and command line, no bug fixed in passing (it goes in the report), one commit per module on `refactor/<language>-readability-<module>`, never pushed to `main` without the owner's validation. A new test must fail when the rule it pins is broken.
