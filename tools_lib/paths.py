"""Path normalization, tolerant matching, and scope enforcement for tools.py."""

import os
import unicodedata

from tools_lib import config as cfg


def loose(name):
    """Comparison form of a name: no case, no non-breaking space, no curly apostrophe."""
    name = unicodedata.normalize("NFC", name).replace("\u00a0", " ").replace("\u202f", " ")
    return name.replace("\u2019", "'").strip().lower()


def tolerant(path):
    """Finds a path dictated approximately: without the exact case or the extension, or with
    "Téléchargements" for Downloads. An item is only taken if it is the only one to match."""
    if os.path.lexists(path):
        return path
    parts = os.path.relpath(path, cfg.ROOT).split("/") if path.startswith(cfg.ROOT + "/") else None
    if not parts or parts[0] == "..":
        return path
    if cfg.AT_HOME and not os.path.lexists(os.path.join(cfg.ROOT, parts[0])):
        parts[0] = cfg.FRENCH_DIRS.get(parts[0].lower(), parts[0])
    current = cfg.ROOT
    for part in parts:
        candidate = os.path.join(current, part)
        if not os.path.lexists(candidate):
            try:
                names_here = os.listdir(current)
            except OSError:
                return os.path.join(current, *parts[parts.index(part) :])
            low = loose(part)
            matches = [n for n in names_here if loose(n) == low] or [
                n for n in names_here if loose(os.path.splitext(n)[0]) == low
            ]
            if len(matches) == 1:
                candidate = os.path.join(current, matches[0])
        current = candidate
    return current


def show(path):
    """A path as the model sees it: ~/... on the Mac, relative to the root elsewhere."""
    if not cfg.AT_HOME:
        return (
            "la racine"
            if path == cfg.ROOT
            else os.path.relpath(path, cfg.ROOT)
            if path.startswith(cfg.ROOT + "/")
            else path
        )
    return (
        "~" if path == cfg.HOME else "~/" + os.path.relpath(path, cfg.HOME) if path.startswith(cfg.HOME + "/") else path
    )


def resolve(path, must_exist=True):
    """Real absolute path, refused if it leaves the scope (outside the root, hidden, or in Library on the Mac)."""
    path = (path or "").strip()
    if path in ("", "~", ".", "/"):
        path = cfg.ROOT
    if path.startswith("~") and not cfg.AT_HOME:  # off the Mac, "~" means the root of the files
        path = cfg.ROOT + path[1:]
    path = os.path.expanduser(path)
    if not os.path.isabs(path) or (not cfg.AT_HOME and not path.startswith(cfg.ROOT)):
        path = os.path.join(cfg.ROOT, path.lstrip("/"))
    real = os.path.realpath(tolerant(os.path.normpath(path)))
    if real != cfg.ROOT and not real.startswith(cfg.ROOT + "/"):
        raise cfg.Refusal(f"{path} est hors {'du dossier personnel' if cfg.AT_HOME else 'de ses fichiers'}.")
    rel = os.path.relpath(real, cfg.ROOT)
    first = rel.split("/")[0]
    if rel != "." and first.startswith("."):
        raise cfg.Refusal(f"{show(real)} est un élément caché, inaccessible.")
    if cfg.AT_HOME and first == "Library" and not (rel + "/").startswith("Library/CloudStorage/"):
        raise cfg.Refusal(f"{show(real)} est dans Library, inaccessible (sauf Google Drive).")
    if must_exist and not os.path.lexists(real):
        raise cfg.Refusal(f"{show(real)} n'existe pas.")
    return real


def protected_root(real):
    """The root, and what is mounted in it (Library/CloudStorage on the Mac), is never moved or deleted."""
    if cfg.AT_HOME:
        return real == cfg.HOME or os.path.dirname(real) == os.path.join(cfg.HOME, "Library/CloudStorage")
    return real == cfg.ROOT or os.path.dirname(real) == cfg.ROOT


def into_dir(source, destination):
    """Final destination: inside the target folder if it exists, or if it is written with a final /
    ("Export/": the folder will be created), otherwise a new name."""
    dest = resolve(destination, must_exist=False)
    if os.path.isdir(dest) or destination.strip().endswith("/"):
        dest = os.path.join(dest, os.path.basename(source))
        resolve(dest, must_exist=False)
    if os.path.lexists(dest):
        raise cfg.Refusal(f"{show(dest)} existe déjà ; je n'écrase rien en déplaçant ou en copiant.")
    return dest


def names(paths):
    """Up to five names, for a description said aloud."""
    shown = [os.path.basename(p) or show(p) for p in paths[:5]]
    more = f" et {len(paths) - 5} autres" if len(paths) > 5 else ""
    return ", ".join(shown) + more
