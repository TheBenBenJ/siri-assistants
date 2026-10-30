#!/usr/bin/env python3
"""Génère et signe les raccourcis Siri conversationnels, utilisables sur le Mac et sur l'iPhone.

    python3 build-shortcuts.py <nom Tailscale du Mac>     # ex. mon-mac.tailnet.ts.net

Chaque raccourci lance les scripts sur le Mac par SSH, via Tailscale : il marche donc sur les deux
appareils. Il appelle `<script> --reset`, puis boucle question → réponse. La réponse sert d'invite
à la question suivante : Siri la lit, puis réécoute. Le script répond __fin__ à « merci »,
« stop »… et le raccourci s'arrête.

La clé SSH de chaque appareil (une par appareil, créée par Raccourcis) doit figurer dans
~/.ssh/authorized_keys du Mac, limitée à ~/.local/bin/ask-ssh. Les .shortcut signés sont écrits à
côté de ce fichier : il suffit de les ouvrir pour les importer.
"""
import getpass
import plistlib
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
if len(sys.argv) != 2:
    sys.exit("usage : build-shortcuts.py <nom Tailscale du Mac>")
SSH_HOST = sys.argv[1]
SSH_USER = getpass.getuser()
SHORTCUTS = {"Appelle Claude": "ask-haiku", "Appelle Gemma": "ask-local"}  # Gemma n'est qu'un nom : ask-local interroge Qwen
OBJECT = "￼"  # marque l'emplacement d'une variable dans un texte


def new_uuid():
    return str(uuid.uuid4()).upper()


def action(identifier, **params):
    return {"WFWorkflowActionIdentifier": identifier, "WFWorkflowActionParameters": params}


def output_of(action_uuid, name):
    return {"OutputName": name, "OutputUUID": action_uuid, "Type": "ActionOutput"}


def attachment(value):
    return {"Value": value, "WFSerializationType": "WFTextTokenAttachment"}


def text_with(prefix, value):
    """Texte fait d'un préfixe fixe suivi d'une variable."""
    return {
        "Value": {"attachmentsByRange": {f"{{{len(prefix)}, 1}}": value}, "string": prefix + OBJECT},
        "WFSerializationType": "WFTextTokenString",
    }


def remote(script):
    """Exécute `script` sur le Mac par SSH, avec la clé SSH de l'appareil qui lance le raccourci."""
    action_uuid = new_uuid()
    return action_uuid, action("is.workflow.actions.runsshscript", UUID=action_uuid,
                               WFSSHAuthenticationType="SSH Key", WFSSHHost=SSH_HOST,
                               WFSSHUser=SSH_USER, WFSSHScript=script)


def workflow(command):
    first_ask, next_ask, loop, stop = (new_uuid() for _ in range(4))
    _, reset = remote(f"{command} --reset")
    # La question suit la commande : ask-ssh la transmet au script sans jamais l'exécuter.
    answer_uuid, chat = remote(text_with(f"{command} --chat ", {"Type": "Variable", "VariableName": "Question"}))
    answer = output_of(answer_uuid, "Résultat du script")
    # Raccourcis peut voir la sortie d'un script comme un fichier : il faut la lire comme texte
    # pour la comparer, sinon le « Si » échoue avec « Choisissez une valeur pour chaque paramètre ».
    answer_as_text = dict(answer, Aggrandizements=[
        {"CoercionItemClass": "WFStringContentItem", "Type": "WFCoercionVariableAggrandizement"}])
    actions = [
        reset,
        action("is.workflow.actions.ask", UUID=first_ask, WFAskActionPrompt="Que veux-tu savoir ?",
               WFInputType="Text"),
        action("is.workflow.actions.setvariable", WFVariableName="Question",
               WFInput=attachment(output_of(first_ask, "Entrée fournie"))),
        action("is.workflow.actions.repeat.count", GroupingIdentifier=loop, WFControlFlowMode=0,
               WFRepeatCount=50),
        chat,
        # WFCondition 4 = « est » ; le script renvoie exactement __fin__, sans retour à la ligne.
        action("is.workflow.actions.conditional", GroupingIdentifier=stop, WFControlFlowMode=0,
               WFCondition=4, WFConditionalActionString="__fin__",
               WFInput={"Type": "Variable", "Variable": attachment(answer_as_text)}),
        action("is.workflow.actions.showresult", Text="À bientôt !"),
        action("is.workflow.actions.exit"),
        action("is.workflow.actions.conditional", GroupingIdentifier=stop, WFControlFlowMode=2, UUID=new_uuid()),
        action("is.workflow.actions.ask", UUID=next_ask, WFAskActionPrompt=text_with("", answer),
               WFInputType="Text"),
        action("is.workflow.actions.setvariable", WFVariableName="Question",
               WFInput=attachment(output_of(next_ask, "Entrée fournie"))),
        action("is.workflow.actions.repeat.count", GroupingIdentifier=loop, WFControlFlowMode=2, UUID=new_uuid()),
    ]
    return {
        "WFWorkflowActions": actions,
        "WFWorkflowClientVersion": "4711",
        "WFWorkflowIcon": {"WFWorkflowIconGlyphNumber": 59511, "WFWorkflowIconStartColor": 4282601983},
        "WFWorkflowImportQuestions": [],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem"],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": [],
    }


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for name, script in SHORTCUTS.items():
            unsigned = Path(tmp) / f"{script}.shortcut"
            with unsigned.open("wb") as f:
                plistlib.dump(workflow(script), f, fmt=plistlib.FMT_BINARY)
            signed = HERE / f"{name}.shortcut"
            subprocess.run(["shortcuts", "sign", "--mode", "anyone", "--input", str(unsigned),
                            "--output", str(signed)], check=True)
            print(signed)


if __name__ == "__main__":
    main()
