#!/usr/bin/python3 -I
# test_tools.py: offline tests for tools.py and tools_lib/ (no network, no real home folder or Trash).
#
#   python3 -I tests/test_tools.py
#
# The expected texts are French: they are what the local model reads and the user hears.
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, REPO)

import tools  # noqa: E402
from tools_lib import config as cfg  # noqa: E402


def check(ok, text, detail=""):
    if not ok:
        sys.exit(f"FAIL: {text} {detail}")
    print("  ok  " + text)


def expect_refusal(fn, text, fragment=""):
    try:
        out = fn()
    except tools.Refusal as e:
        check(not fragment or fragment in str(e), text, str(e))
        return
    check(False, text, f"expected Refusal, got {out!r}")


def configure_sandbox(root, at_home=False, read_only=False):
    cache = tempfile.mkdtemp(prefix="siri-tools-cache-")
    real_root = os.path.realpath(root)
    cfg.HOME = real_root if at_home else os.path.dirname(real_root)
    cfg.ROOT = real_root
    cfg.AT_HOME = at_home
    cfg.READ_ONLY = read_only
    cfg.PENDING_FILE = os.path.join(cache, "pending.json")
    cfg.ACTIONS_LOG = os.path.join(cache, "actions.log")
    cfg.BRIDGE = "http://127.0.0.1:9"  # unreachable port so bridge_quiet returns "" immediately
    cfg.SCHEMA = cfg.build_schema(at_home=at_home, read_only=read_only, folders="iCloud et Drive")
    return cache


def run_cli(*argv):
    old = sys.argv
    sys.argv = ["tools.py", *argv]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            tools.main()
    finally:
        sys.argv = old
    return buf.getvalue()


def main():
    print("Profile & schema")
    with tempfile.TemporaryDirectory() as folder:
        new_p = os.path.join(folder, "profile.json")
        old_p = os.path.join(folder, "profil.json")
        check(cfg.load_profile([new_p, old_p]) == {}, "no profile returns empty dict")
        with open(old_p, "w", encoding="utf-8") as f:
            json.dump({"racine": "/srv/old", "lecture_seule": True}, f)
        prof = cfg.load_profile([new_p, old_p])
        check(
            cfg.setting("root", "racine", prof) == "/srv/old"
            and cfg.setting("read_only", "lecture_seule", prof) is True,
            "former profil.json French keys are read",
        )
        with open(new_p, "w", encoding="utf-8") as f:
            json.dump({"root": "/srv/new", "read_only": False}, f)
        prof = cfg.load_profile([new_p, old_p])
        check(cfg.setting("root", "racine", prof) == "/srv/new", "profile.json wins over profil.json")
        home_names = {t["name"] for t in cfg.build_schema(at_home=True, read_only=False)}
        ro_names = {t["name"] for t in cfg.build_schema(at_home=False, read_only=True, folders="iCloud")}
        check(cfg.WRITING.issubset(home_names), "Mac schema includes write tools")
        check(
            ro_names.isdisjoint(cfg.WRITING) and "list_dir" in ro_names and "google" in ro_names,
            "read-only server schema strips write tools",
        )

    print("Paths & scope")
    with tempfile.TemporaryDirectory() as base:
        root = os.path.join(base, "home")
        os.makedirs(os.path.join(root, "Downloads"))
        os.makedirs(os.path.join(root, "Library", "CloudStorage", "GoogleDrive"))
        os.makedirs(os.path.join(root, "Library", "Mail"))
        os.makedirs(os.path.join(root, ".ssh"))
        with open(os.path.join(root, "Downloads", "Facture d\u2019avril.txt"), "w", encoding="utf-8") as f:
            f.write("bonjour\n")
        configure_sandbox(root, at_home=True, read_only=False)
        resolved = tools.resolve("Téléchargements/facture d'avril")
        check(
            resolved.endswith("/Downloads/Facture d\u2019avril.txt"),
            "tolerant path resolves French alias, case, apostrophe, and extension",
            resolved,
        )
        expect_refusal(
            lambda: tools.resolve("../outside", must_exist=False), "path traversal outside root refused", "hors"
        )
        expect_refusal(lambda: tools.resolve(".ssh", must_exist=False), "hidden top-level folder refused", "caché")
        expect_refusal(lambda: tools.resolve("Library/Mail"), "Library outside CloudStorage refused", "Library")
        check(tools.resolve("Library/CloudStorage/GoogleDrive").endswith("GoogleDrive"), "Library/CloudStorage allowed")
        check(
            tools.protected_root(cfg.ROOT)
            and tools.protected_root(os.path.join(cfg.ROOT, "Library/CloudStorage/GoogleDrive")),
            "root and CloudStorage mount are protected",
        )

    print("Listing, searching & reading")
    with tempfile.TemporaryDirectory() as base:
        root = os.path.join(base, "srv")
        os.makedirs(os.path.join(root, "iCloud", "Factures"))
        os.makedirs(os.path.join(root, ".hidden"))
        with open(os.path.join(root, "iCloud", "note.txt"), "w", encoding="utf-8") as f:
            f.write("A" * 10 + "B" * 10)
        with open(os.path.join(root, "iCloud", "bin.dat"), "wb") as f:
            f.write(b"\x00\x01\x02binary")
        docx = os.path.join(root, "iCloud", "doc.docx")
        with zipfile.ZipFile(docx, "w") as z:
            z.writestr(
                "word/document.xml", "<w:document><w:body><w:p><w:t>Devis validé</w:t></w:p></w:body></w:document>"
            )
        odt = os.path.join(root, "iCloud", "doc.odt")
        with zipfile.ZipFile(odt, "w") as z:
            z.writestr("content.xml", "<office:text><text:p>Contrat signé</text:p></office:text>")
        html_file = os.path.join(root, "iCloud", "page.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write("<html><style>p{color:red}</style><body><p>Bonjour</p><script>bad()</script></body></html>")
        configure_sandbox(root, at_home=False, read_only=False)

        listed = tools.list_dir("iCloud")
        check(
            "Factures/" in listed and "note.txt" in listed and ".hidden" not in listed,
            "list_dir formats folders and skips hidden items",
            listed,
        )
        found, complete = tools.search_by_name("factures", cfg.ROOT)
        check(
            complete and len(found) == 1 and found[0].endswith("Factures"),
            "search_by_name finds nested folder and skips hidden dirs",
            found,
        )

        old_max = cfg.MAX_READ
        cfg.MAX_READ = 10
        try:
            page1 = tools.read_file("iCloud/note.txt", start=0)
            page2 = tools.read_file("iCloud/note.txt", start=10)
        finally:
            cfg.MAX_READ = old_max
        check("AAAAAAAAAA" in page1 and "start=10" in page1, "read_file paginates long text", page1)
        check("BBBBBBBBBB" in page2 and "start=" not in page2, "read_file second page ends cleanly", page2)
        expect_refusal(lambda: tools.read_file("iCloud/bin.dat"), "read_file refuses binary files", "binaire")
        expect_refusal(lambda: tools.read_file("iCloud"), "read_file refuses directories", "dossier")
        check("Devis validé" in tools.office_text(docx, ".docx"), "office_text reads .docx XML")
        check("Contrat signé" in tools.office_text(odt, ".odt"), "office_text reads .odt XML")
        html_out = tools.office_text(html_file, ".html")
        check(
            "Bonjour" in html_out and "color:red" not in html_out and "bad()" not in html_out,
            "office_text strips style/script from HTML",
            html_out,
        )
        expect_refusal(lambda: tools.office_text(docx, ".doc"), "office_text refuses legacy .doc", "illisible")

    print("Writes, pending confirmation & read-only guard")
    with tempfile.TemporaryDirectory() as base:
        root = os.path.join(base, "work")
        os.makedirs(os.path.join(root, "Docs"))
        configure_sandbox(root, at_home=False, read_only=False)

        out = tools.write_file("Docs/a.txt", "ligne 1", "create")
        check(out.startswith("Fait : création"), "write_file create succeeds immediately", out)
        expect_refusal(
            lambda: tools.write_file("Docs/a.txt", "x", "create"),
            "write_file create refuses existing file",
            "existe déjà",
        )
        tools.write_file("Docs/a.txt", "ligne 2", "append")
        with open(os.path.join(root, "Docs", "a.txt"), encoding="utf-8") as f:
            check(f.read() == "ligne 1\nligne 2\n", "write_file append appends cleanly")

        out = tools.write_file("Docs/a.txt", "remplacé", "overwrite")
        check(out.startswith("EN ATTENTE"), "write_file overwrite queues pending confirmation", out)
        check("remplace le contenu de a.txt" in tools.all_pending_desc(), "pending description exposes real filename")
        done = tools.confirm()
        with open(os.path.join(root, "Docs", "a.txt"), encoding="utf-8") as f:
            check("remplacé" in done and f.read() == "remplacé\n", "confirm applies queued overwrite")

        tools.make_dir("Docs/Sub")
        tools.copy("Docs/a.txt", "Docs/Sub/")
        check(os.path.isfile(os.path.join(root, "Docs", "Sub", "a.txt")), "copy into directory works")

        out = tools.move("Docs/a.txt", "Docs/b.txt")
        check(
            out.startswith("EN ATTENTE") and os.path.exists(os.path.join(root, "Docs", "a.txt")),
            "move waits for confirmation",
        )
        done = tools.confirm()
        check(
            "est maintenant" in done and os.path.exists(os.path.join(root, "Docs", "b.txt")), "confirm runs queued move"
        )

        out = tools.delete(["Docs/b.txt"])
        check(
            out.startswith("EN ATTENTE") and os.path.exists(os.path.join(root, "Docs", "b.txt")),
            "delete waits for confirmation",
        )
        # Expire pending entry
        with open(cfg.PENDING_FILE, encoding="utf-8") as f:
            pending = json.load(f)
        pending["time"] = time.time() - cfg.PENDING_TTL - 5
        with open(cfg.PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(pending, f)
        check(tools.load_pending() is None and not os.path.exists(cfg.PENDING_FILE), "expired pending queue is dropped")

        expect_refusal(
            lambda: tools.delete(["Docs"]),
            "top-level mounted folder cannot be deleted in non-home mode",
            "ne peut pas être supprimé",
        )

        # Read-only CLI guard
        cfg.READ_ONLY = True
        cli_out = run_cli("write_file", json.dumps({"path": "Docs/c.txt", "content": "x", "mode": "create"}))
        check(
            cli_out.startswith("REFUS : ") and "lecture seule" in cli_out,
            "CLI refuses write tools when READ_ONLY",
            cli_out,
        )
        cli_schema = json.loads(run_cli("--schema"))
        check(
            isinstance(cli_schema, list) and cli_schema[0]["type"] == "function",
            "CLI --schema outputs OpenAI function tools",
        )

    print("All good.")


if __name__ == "__main__":
    main()
