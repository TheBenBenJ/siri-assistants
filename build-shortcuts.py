#!/usr/bin/env python3
"""Builds and signs the two conversational Siri shortcuts, usable on the Mac and on the iPhone.

    python3 build-shortcuts.py <Tailscale name of the Mac>   # e.g. my-mac.tailnet.ts.net
    python3 build-shortcuts.py <server name> <account>       # assistants installed on a server, under that account

Each shortcut runs the scripts on that machine over SSH, through Tailscale, so the same shortcut works on both
devices. It calls `<script> --reset`, then loops question -> answer. The answer is the prompt of the next question:
Siri reads it aloud, then listens again. The script answers __fin__ to "merci", "stop"... and the shortcut stops.

Each device's SSH key (one per device, created by Shortcuts) must be in that machine's ~/.ssh/authorized_keys,
restricted to ask-ssh. The signed .shortcut files are written next to this file: open them to import them.
Needs macOS, for `shortcuts sign`. Names and texts are French: they are what Siri hears and says.
"""
import getpass
import plistlib
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
if len(sys.argv) not in (2, 3):
    sys.exit("usage : build-shortcuts.py <nom Tailscale de la machine> [compte, par défaut le tien]")
SSH_HOST = sys.argv[1]
SSH_USER = sys.argv[2] if len(sys.argv) == 3 else getpass.getuser()
# The shortcut's name is the Siri phrase. "Gemma" is only a name: ask-local asks Qwen, a word Siri mishears.
SHORTCUTS = {"Appelle Claude": "ask-haiku", "Appelle Gemma": "ask-local"}
OBJECT = "￼"  # U+FFFC, marks where a variable sits in a text


def new_uuid():
    return str(uuid.uuid4()).upper()


def action(identifier, **params):
    return {"WFWorkflowActionIdentifier": identifier, "WFWorkflowActionParameters": params}


def output_of(action_uuid, name):
    return {"OutputName": name, "OutputUUID": action_uuid, "Type": "ActionOutput"}


def attachment(value):
    return {"Value": value, "WFSerializationType": "WFTextTokenAttachment"}


def text_with(prefix, value):
    """Text made of a fixed prefix followed by a variable."""
    return {
        "Value": {"attachmentsByRange": {f"{{{len(prefix)}, 1}}": value}, "string": prefix + OBJECT},
        "WFSerializationType": "WFTextTokenString",
    }


def remote(script):
    """Runs `script` on the machine over SSH, with the SSH key of the device that runs the shortcut."""
    action_uuid = new_uuid()
    return action_uuid, action("is.workflow.actions.runsshscript", UUID=action_uuid,
                               WFSSHAuthenticationType="SSH Key", WFSSHHost=SSH_HOST,
                               WFSSHUser=SSH_USER, WFSSHScript=script)


def workflow(command):
    """The shortcut: reset, ask, then up to 50 rounds of answer-as-prompt, until the script says __fin__."""
    first_ask, next_ask, loop, stop = (new_uuid() for _ in range(4))
    _, reset = remote(f"{command} --reset")
    # The question follows the command: ask-ssh hands it to the script, never runs it.
    answer_uuid, chat = remote(text_with(f"{command} --chat ", {"Type": "Variable", "VariableName": "Question"}))
    answer = output_of(answer_uuid, "Résultat du script")
    # Shortcuts may see a script's output as a file: it must be read as text to be compared, otherwise the "If" fails
    # with "Choisissez une valeur pour chaque paramètre" (choose a value for each parameter).
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
        # WFCondition 4 = "is"; the script returns exactly __fin__, without a newline.
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
