#!/usr/bin/python3 -I
# essai-recap.py : rejoue recap sur des fichiers de récap fabriqués, sans iCloud : frais, vieux, périmé, absent, illisible.
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

ICI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, ICI)
loader = importlib.machinery.SourceFileLoader("recap", os.path.join(ICI, "recap"))
spec = importlib.util.spec_from_loader("recap", loader)
recap = importlib.util.module_from_spec(spec)
loader.exec_module(recap)

NOW = datetime.datetime(2026, 10, 31, 19, 47)
FRESH = {"lecture": "consigne de lecture", "date": "2026-10-31", "genere_a": "2026-10-31T19:40", "a_dire": "Samedi 31 octobre. Rien à l'agenda.", "a_faire": [{"titre": "Appeler le garage"}]}


def check(ok, text, detail=""):
    if not ok:
        sys.exit(f"ÉCHEC : {text} {detail}")
    print("  ok  " + text)


def main():
    print("Récap du jour")
    said = recap.for_model(FRESH, NOW)
    check(said.startswith(recap.UNTRUSTED), "pour le modèle, le récap est présenté comme une donnée, pas une consigne")
    check("À dire : Samedi 31 octobre. Rien à l'agenda.\n" in said, "le texte à lire est là, sans avertissement")
    check('"Appeler le garage"' in said and '"lecture"' not in said and '"a_dire"' not in said, "les détails suivent, sans doublon")
    check(recap.to_say(FRESH, NOW) == "Samedi 31 octobre. Rien à l'agenda.", "--dire : le texte seul, sans rien autour")

    said = recap.to_say({**FRESH, "genere_a": "2026-10-31T09:10"}, NOW)
    check(said.startswith("Attention, ce récap date de 9 h 10. Samedi"), "un récap du jour vieux de plus de 3 heures le dit", said)
    check("Attention" not in recap.to_say({**FRESH, "genere_a": "2026-10-31T17:00"}, NOW), "moins de 3 heures : pas d'avertissement")
    check("Attention" not in recap.to_say({**FRESH, "genere_a": "2026-10-31T19:40+01:00"}, NOW), "une heure avec décalage horaire est comprise")

    old = {**FRESH, "date": "2026-10-30", "genere_a": "2026-10-30T23:50"}
    expected = "Le récap du jour n'est pas prêt : le dernier date de vendredi 30 octobre, à 23 h 50."
    check(recap.to_say(old, NOW) == expected, "le récap d'hier n'est pas lu comme celui d'aujourd'hui", recap.to_say(old, NOW))
    check(recap.for_model(old, NOW) == "À dire : " + expected, "le modèle n'en a pas non plus les détails", recap.for_model(old, NOW))

    print("Fichier")
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "Recap du jour.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(FRESH, f)
        check(recap.read_recap(path)["date"] == "2026-10-31", "le fichier est lu")

        # Fichier resté dans le cloud : open échoue (Errno 11 sous launchd) jusqu'à ce que brctl l'ait fait redescendre.
        real_open, real_run, real_sleep = open, recap.subprocess.run, recap.time.sleep
        attempts, asked = [], []

        def cloud_open(*args, **kwargs):
            attempts.append(args[0])
            if len(attempts) < 3:
                raise OSError(11, "Resource deadlock avoided")
            return real_open(*args, **kwargs)
        recap.open, recap.subprocess.run, recap.time.sleep = cloud_open, lambda command, **k: asked.append(command), lambda s: None
        check(recap.read_recap(path)["date"] == "2026-10-31" and len(asked) == 1 and "download" in asked[0], "un fichier resté dans le cloud est redescendu une fois, puis lu")
        recap.open = lambda *a, **k: (_ for _ in ()).throw(OSError(11, "Resource deadlock avoided"))
        try:
            recap.read_recap(path)
            check(False, "un fichier qui ne redescend pas le dit")
        except OSError:
            check(True, "un fichier qui ne redescend pas le dit")
        del recap.open
        recap.subprocess.run, recap.time.sleep = real_run, real_sleep

        link = os.path.join(folder, "recap")
        os.symlink(os.path.join(ICI, "recap"), link)
        done = subprocess.run([link], capture_output=True, text=True, env={})
        check("Traceback" not in done.stderr, "lancée par son lien et sans environnement, la commande trouve spoken_dates", done.stderr)

        recap.FICHIER = path
        sys.argv = ["recap", "--dire"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            recap.main()
        check("Détails" not in out.getvalue() and "À dire" not in out.getvalue(), "recap --dire n'écrit que le texte", out.getvalue())
        sys.argv = ["recap"]

        recap.FICHIER = os.path.join(folder, "absent.json")
        for content, text, expected in ((None, "un fichier absent le dit, sans trace d'erreur", "Le récap du jour n'est pas dans iCloud"),
                                        ("{coupé", "un fichier illisible le dit", "illisible"),
                                        ('{"date": "2026-10-31"}', "un fichier incomplet le dit", "illisible")):
            if content is not None:
                recap.FICHIER = path
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            try:
                recap.main()
                check(False, text)
            except SystemExit as e:
                check(expected in str(e.code), text, e.code)


if __name__ == "__main__":
    main()
