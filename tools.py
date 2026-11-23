#!/usr/bin/python3 -I
"""tools.py: the local model's tools (ask-local's tool calls): files, tasks, the daily recap and the Google account.

Run by ask-gemini and ask-local from the folder they are in (their real path, links followed):
  tools.py --schema            tool definitions, in the "tools" format of the OpenAI chat API
  tools.py <tool> '<json>'     runs a tool and prints its result, for the model
  tools.py --pending           describes what waits for the user's "oui", if anything
  tools.py --confirm           runs it
  tools.py --cancel            forgets it

Implementation lives in the sibling package tools_lib/. This entrypoint preserves the CLI interface
and public re-exports for callers and offline tests.
"""

import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

_HERE = os.path.dirname(os.path.realpath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from tools_lib import config as _cfg  # noqa: E402
from tools_lib.config import (  # noqa: E402, F401
    ACTIONS_LOG,
    AT_HOME,
    BRIDGE,
    FRENCH_DIRS,
    HOME,
    MAX_LIST,
    MAX_READ,
    MAX_SEARCH,
    PENDING_FILE,
    PENDING_TTL,
    PROFILE,
    PROFILE_FILES,
    READ_ONLY,
    ROOT,
    SCHEMA,
    TEXTUTIL_EXT,
    WRITING,
    Refusal,
    build_schema,
    load_profile,
    log_action,
    setting,
)
from tools_lib.files import (  # noqa: E402, F401
    TOOLS,
    TextOnly,
    add_task,
    copy,
    delete,
    google,
    list_dir,
    make_dir,
    move,
    office_text,
    read_file,
    recap,
    search,
    search_by_name,
    write_file,
)
from tools_lib.paths import (  # noqa: E402, F401
    into_dir,
    loose,
    names,
    protected_root,
    resolve,
    show,
    tolerant,
)
from tools_lib.pending import (  # noqa: E402, F401
    all_pending_desc,
    bridge,
    bridge_quiet,
    confirm,
    load_pending,
    pending_desc,
    run_confirmed,
    set_pending,
)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if arg == "--schema":
            print(json.dumps([{"type": "function", "function": t} for t in _cfg.SCHEMA], ensure_ascii=False))
        elif arg == "--pending":
            print(all_pending_desc(), end="")
        elif arg == "--confirm":
            sent = bridge_quiet("/confirmer")
            done = confirm() if load_pending() else ""
            print(" ".join(x for x in (done, sent) if x) or "Il n'y a plus rien à confirmer.", end="")
        elif arg == "--cancel":
            bridge_quiet("/annuler")
            if os.path.exists(_cfg.PENDING_FILE):
                os.remove(_cfg.PENDING_FILE)
        elif arg in _cfg.WRITING and _cfg.READ_ONLY:
            raise Refusal("ici, les fichiers sont en lecture seule : rien ne peut être écrit, déplacé ni supprimé.")
        elif arg in TOOLS:
            args = json.loads(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].strip() else {}
            print(TOOLS[arg](**args), end="")
        else:
            print(f"ERREUR : outil inconnu « {arg} ».", end="")
    except Refusal as e:
        print(f"REFUS : {e}", end="")
    except (TypeError, ValueError) as e:
        print(f"ERREUR : arguments invalides pour {arg} ({e}).", end="")
    except (OSError, subprocess.SubprocessError) as e:
        print(f"ERREUR : {e}", end="")


if __name__ == "__main__":
    main()
