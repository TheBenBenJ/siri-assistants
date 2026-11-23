"""Pending confirmation queue and Google bridge HTTP client for tools.py."""
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from tools_lib import config as cfg
from tools_lib.paths import names, resolve, show


def bridge(path, body=None, timeout=90):
    """Call to the Google bridge; Google proposals live there, out of the model's reach."""
    request = urllib.request.Request(cfg.BRIDGE + path, json.dumps(body or {}).encode(), {"X-Assistant": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
            return response.read().decode()
    except urllib.error.HTTPError as e:
        raise cfg.Refusal(e.read().decode(errors="replace")) from e


def bridge_quiet(path):
    """For --pending, --confirm and --cancel: with no bridge running, nothing waits there."""
    try:
        return bridge(path, timeout=30)
    except (OSError, cfg.Refusal):
        return ""


def load_pending():
    """The file actions waiting for the "oui", or None; they are dropped after PENDING_TTL."""
    try:
        with open(cfg.PENDING_FILE) as f:
            pending = json.load(f)
    except (OSError, ValueError):
        return None
    if time.time() - pending.get("time", 0) > cfg.PENDING_TTL or "actions" not in pending:
        os.remove(cfg.PENDING_FILE)
        return None
    return pending


def set_pending(action, args, desc):
    """Adds the action to those waiting for the "oui". One turn may queue several (tidying a folder), and a single
    "oui" runs them all: keeping only the last one once left a real tidy-up half done. Anything else cancels them."""
    pending = load_pending() or {"actions": []}
    pending["actions"].append({"action": action, "args": args, "desc": desc})
    pending["time"] = time.time()
    os.makedirs(os.path.dirname(cfg.PENDING_FILE), exist_ok=True)
    with open(cfg.PENDING_FILE, "w") as f:
        json.dump(pending, f)
    return f"EN ATTENTE DE CONFIRMATION : {desc} Rien n'est fait tant que l'utilisateur n'a pas dit oui."


def pending_desc(pending):
    descs = [a["desc"] for a in pending["actions"]]
    if len(descs) == 1:
        return descs[0]
    return f"Je fais {len(descs)} changements. " + " ".join(descs)


def all_pending_desc():
    """What waits for the "oui": file actions here, Google actions in the bridge."""
    pending = load_pending()
    return " ".join(x for x in (pending_desc(pending) if pending else "", bridge_quiet("/attente")) if x)


def run_confirmed(action, args):
    # Paths are checked again: the disk may have changed since the question.
    if action == "delete":
        reals = [resolve(p) for p in args["paths"]]
        subprocess.run(["/usr/bin/trash"] + reals, check=True, capture_output=True, text=True)
        for r in reals:
            cfg.log_action(f"trash {show(r)}")
        return f"C'est fait : {names(reals)} {'sont' if len(reals) > 1 else 'est'} à la Corbeille."
    if action == "move":
        src = resolve(args["source"])
        dest = resolve(args["destination"], must_exist=False)
        if os.path.lexists(dest):
            raise cfg.Refusal(f"{show(dest)} existe maintenant ; je n'écrase rien.")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        cfg.log_action(f"move {show(src)} → {show(dest)}")
        return f"C'est fait : {os.path.basename(src)} est maintenant {show(dest)}."
    if action == "write_file":
        real = resolve(args["path"], must_exist=False)
        content = args["content"]
        with open(real, "w") as f:
            f.write(content if content.endswith("\n") else content + "\n")
        cfg.log_action(f"overwrite {show(real)}")
        return f"C'est fait : {os.path.basename(real)} est remplacé."
    return "Action inconnue, rien n'est fait."


def confirm():
    pending = load_pending()
    if not pending:
        return "Il n'y a plus rien à confirmer."
    os.remove(cfg.PENDING_FILE)
    done, failures = [], []
    for action in pending["actions"]:
        try:
            done.append(run_confirmed(action["action"], action["args"]))
        except (cfg.Refusal, OSError, subprocess.SubprocessError) as e:
            failures.append(f"Échec pour « {action['desc']} » : {e}")
    if len(pending["actions"]) == 1:
        return " ".join(done + failures)
    summary = f"C'est fait : {len(done)} changements sur {len(pending['actions'])}." if done else ""
    return " ".join([summary] + failures).strip()
