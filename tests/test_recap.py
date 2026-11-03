#!/usr/bin/python3 -I
# test_recap.py: replays recap on hand-made recap files, without iCloud: fresh, old, stale, missing, unreadable.
#
#   python3 -I tests/test_recap.py
#
# The expected texts are French: they are what the user hears.
import contextlib
import datetime
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ["TZ"] = "Europe/Paris"  # the expected times below are Paris times
time.tzset()
REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, REPO)
loader = importlib.machinery.SourceFileLoader("recap", os.path.join(REPO, "recap"))
spec = importlib.util.spec_from_loader("recap", loader)
recap = importlib.util.module_from_spec(spec)
loader.exec_module(recap)

NOW = datetime.datetime(2026, 10, 31, 19, 47)
FRESH = {"lecture": "consigne de lecture", "date": "2026-10-31", "genere_a": "2026-10-31T19:40", "a_dire": "Samedi 31 octobre. Rien à l'agenda.", "a_faire": [{"titre": "Appeler le garage"}]}


def check(ok, text, detail=""):
    if not ok:
        sys.exit(f"FAIL: {text} {detail}")
    print("  ok  " + text)


def main():
    print("Daily recap")
    said = recap.for_model(FRESH, NOW)
    check(said.startswith(recap.UNTRUSTED), "for the model, the recap is presented as data, not an instruction")
    check("À dire : Samedi 31 octobre. Rien à l'agenda.\n" in said, "the text to read is there, without a warning")
    check('"Appeler le garage"' in said and '"lecture"' not in said and '"a_dire"' not in said, "the details follow, without duplicates")
    check(recap.to_say(FRESH, NOW) == "Samedi 31 octobre. Rien à l'agenda.", "--dire: the text alone, nothing around it")

    said = recap.to_say({**FRESH, "genere_a": "2026-10-31T09:10"}, NOW)
    check(said.startswith("Attention, ce récap date de 9 h 10. Samedi"), "a recap of the day older than 3 hours says so", said)
    check("Attention" not in recap.to_say({**FRESH, "genere_a": "2026-10-31T17:00"}, NOW), "under 3 hours: no warning")
    check("Attention" not in recap.to_say({**FRESH, "genere_a": "2026-10-31T19:40+01:00"}, NOW), "a time with a UTC offset is understood")

    old = {**FRESH, "date": "2026-10-30", "genere_a": "2026-10-30T23:50"}
    expected = "Le récap du jour n'est pas prêt : le dernier date de vendredi 30 octobre, à 23 h 50."
    check(recap.to_say(old, NOW) == expected, "yesterday's recap is not read as today's", recap.to_say(old, NOW))
    check(recap.for_model(old, NOW) == "À dire : " + expected, "nor does the model get its details", recap.for_model(old, NOW))

    print("File")
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "Recap du jour.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(FRESH, f)
        check(recap.read_recap(path)["date"] == "2026-10-31", "the file is read")

        # A file left in the cloud: open fails (Errno 11 under launchd) until brctl has downloaded it.
        real_open, real_run, real_sleep = open, recap.subprocess.run, recap.time.sleep
        attempts, asked = [], []

        def cloud_open(*args, **kwargs):
            attempts.append(args[0])
            if len(attempts) < 3:
                raise OSError(11, "Resource deadlock avoided")
            return real_open(*args, **kwargs)
        recap.open, recap.subprocess.run, recap.time.sleep = cloud_open, lambda command, **k: asked.append(command), lambda s: None
        check(recap.read_recap(path)["date"] == "2026-10-31" and len(asked) == 1 and "download" in asked[0], "a file left in the cloud is downloaded once, then read")
        recap.open = lambda *a, **k: (_ for _ in ()).throw(OSError(11, "Resource deadlock avoided"))
        try:
            recap.read_recap(path)
            check(False, "a file that does not come down says so")
        except OSError:
            check(True, "a file that does not come down says so")
        del recap.open
        recap.subprocess.run, recap.time.sleep = real_run, real_sleep

        link = os.path.join(folder, "recap")
        os.symlink(os.path.join(REPO, "recap"), link)
        done = subprocess.run([link], capture_output=True, text=True, env={})
        check("Traceback" not in done.stderr, "run through its link and without environment, the command finds spoken_dates", done.stderr)

        recap.RECAP_FILE = path
        sys.argv = ["recap", "--dire"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            recap.main()
        check("Détails" not in out.getvalue() and "À dire" not in out.getvalue(), "recap --dire only writes the text", out.getvalue())
        sys.argv = ["recap"]

        recap.RECAP_FILE = os.path.join(folder, "absent.json")
        for content, text, expected in ((None, "a missing file says so, without a traceback", "Le récap du jour n'est pas dans iCloud"),
                                        ("{coupé", "an unreadable file says so", "illisible"),
                                        ('{"date": "2026-10-31"}', "an incomplete file says so", "illisible")):
            if content is not None:
                recap.RECAP_FILE = path
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            try:
                recap.main()
                check(False, text)
            except SystemExit as e:
                check(expected in str(e.code), text, e.code)

    print("Profile")
    with tempfile.TemporaryDirectory() as folder:
        new, former = os.path.join(folder, "profile.json"), os.path.join(folder, "profil.json")
        recap.PROFILE_FILES = [new, former]
        check(recap.profile_recap() is None, "no profile: the default path")
        with open(former, "w") as f:
            json.dump({"racine": "/srv", "recap": "/srv/former.json"}, f)
        check(recap.profile_recap() == "/srv/former.json", "the former profil.json is still read")
        with open(new, "w") as f:
            json.dump({"root": "/srv", "recap": "/srv/new.json"}, f)
        check(recap.profile_recap() == "/srv/new.json", "profile.json is preferred")
    print("All good.")


if __name__ == "__main__":
    main()
