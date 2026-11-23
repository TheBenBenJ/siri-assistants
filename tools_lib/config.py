"""Profile loading, constants, OpenAI tool schema, and shared primitives for tools.py."""

import copy
import json
import os
import pwd
import time

HOME = pwd.getpwuid(os.getuid()).pw_dir
PROFILE_FILES = [os.path.join(HOME, ".config/siri-assistants", name) for name in ("profile.json", "profil.json")]


def load_profile(profile_files=None):
    """The server profile: profile.json, or the former profil.json without a readable profile.json; {} on the Mac."""
    files = profile_files if profile_files is not None else PROFILE_FILES
    path = next((p for p in files if os.access(p, os.R_OK)), files[-1])
    try:
        with open(path) as f:
            return json.load(f)
    except OSError, ValueError:
        return {}


def setting(key, former_key, profile=None):
    """A profile value under its English key, else under the French key of a former profile (like jq's //)."""
    src = PROFILE if profile is None else profile
    value = src.get(key)
    return src.get(former_key) if value is None or value is False else value


PROFILE = load_profile()
ROOT = os.path.realpath(setting("root", "racine") or HOME)
AT_HOME = ROOT == os.path.realpath(HOME)  # the Mac: the home folder, with its own rules (Library, Spotlight, Trash)
READ_ONLY = bool(setting("read_only", "lecture_seule"))
WRITING = {"write_file", "make_dir", "copy", "move", "delete"}
BRIDGE = "http://127.0.0.1:8766"
PENDING_FILE = os.path.join(HOME, ".cache/ask-local/pending.json")
ACTIONS_LOG = os.path.join(HOME, ".cache/ask/actions.log")
PENDING_TTL = 600  # a confirmation more than 10 minutes after the question is ignored
MAX_READ = 6000  # characters per read; the model asks for the rest with start
MAX_LIST = 150
MAX_SEARCH = 30
# Folders as the user says them, to their real names on macOS.
FRENCH_DIRS = {
    "téléchargements": "Downloads",
    "telechargements": "Downloads",
    "bureau": "Desktop",
    "images": "Pictures",
    "photos": "Pictures",
    "musique": "Music",
    "vidéos": "Movies",
    "videos": "Movies",
    "films": "Movies",
    "google drive": "Google Drive",
}
TEXTUTIL_EXT = {
    ".doc",
    ".docx",
    ".rtf",
    ".rtfd",
    ".html",
    ".htm",
    ".odt",
    ".webarchive",
    ".wordml",
}  # what textutil converts

# Base tool definitions seen by the model. French, like its prompt: they shape its French replies.
BASE_SCHEMA = [
    {
        "name": "list_dir",
        "description": "Liste le contenu d'un dossier (dossiers suivis de /).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Dossier, relatif au dossier personnel : Documents, Desktop (Bureau), Downloads (Téléchargements), Google Drive…",
                },
                "sort": {
                    "type": "string",
                    "enum": ["nom", "recent"],
                    "description": "recent : les plus récemment modifiés d'abord, avec leur date.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search",
        "description": "Cherche des fichiers par nom ou par contenu (Spotlight).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mots à chercher."},
                "folder": {
                    "type": "string",
                    "description": "Dossier où chercher ; par défaut tout le dossier personnel.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Lit un fichier texte, PDF ou Word.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start": {"type": "integer", "description": "Position de départ en caractères, pour lire la suite."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Écrit un fichier texte. create : nouveau fichier ; append : ajoute à la fin ; overwrite : remplace un fichier existant (demande confirmation).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["create", "append", "overwrite"]},
            },
            "required": ["path", "content", "mode"],
        },
    },
    {
        "name": "make_dir",
        "description": "Crée un dossier.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "copy",
        "description": "Copie un fichier ou un dossier. Si la destination est un dossier existant, copie dedans.",
        "parameters": {
            "type": "object",
            "properties": {"source": {"type": "string"}, "destination": {"type": "string"}},
            "required": ["source", "destination"],
        },
    },
    {
        "name": "move",
        "description": "Déplace ou renomme un fichier ou un dossier (demande confirmation). Si la destination est un dossier existant, déplace dedans.",
        "parameters": {
            "type": "object",
            "properties": {"source": {"type": "string"}, "destination": {"type": "string"}},
            "required": ["source", "destination"],
        },
    },
    {
        "name": "delete",
        "description": "Met des fichiers ou dossiers à la Corbeille (demande confirmation).",
        "parameters": {
            "type": "object",
            "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
            "required": ["paths"],
        },
    },
    {
        "name": "add_task",
        "description": "Ajoute une tâche à la liste de l'utilisateur (Google Tasks et dashboard). Immédiat, sans confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "La tâche, courte, dans les mots de l'utilisateur."},
                "due": {
                    "type": "string",
                    "description": "Échéance telle que l'utilisateur la dit, sans la calculer (vendredi, demain, 3 novembre), seulement s'il en donne une.",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "google",
        "description": "Son compte Google. Lire, immédiat : mails (requete : recherche Gmail, boîte de réception par défaut), mail (numero), contact (requete), agenda (jours), drive (requete), document (numero), taches, notes (requete : ses notes Keep). Agir, demande confirmation : repondre (numero, texte), envoyer (a, objet, texte), brouillon (a, objet, texte), archiver (numero), corbeille (numero), rdv (titre, quand, duree, lieu), annuler-rdv (numero). numero : celui de la dernière liste.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "mails",
                        "mail",
                        "contact",
                        "agenda",
                        "drive",
                        "document",
                        "taches",
                        "notes",
                        "repondre",
                        "envoyer",
                        "brouillon",
                        "archiver",
                        "corbeille",
                        "rdv",
                        "annuler-rdv",
                    ],
                },
                "requete": {"type": "string"},
                "numero": {"type": "integer"},
                "suite": {"type": "integer", "description": "Position de départ, pour lire la suite."},
                "jours": {"type": "integer"},
                "a": {
                    "type": "string",
                    "description": "Adresse, nom d'un contact, ou moi pour l'utilisateur lui-même.",
                },
                "objet": {"type": "string"},
                "texte": {"type": "string"},
                "titre": {"type": "string"},
                "quand": {
                    "type": "string",
                    "description": "Tel que l'utilisateur le dit, sans le calculer : vendredi 14h, demain à 9 h 30.",
                },
                "duree": {"type": "integer", "description": "En minutes."},
                "lieu": {"type": "string"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "recap",
        "description": "Son récap du jour : météo, agenda, à faire, mails à traiter. Pour « mon récap », « résume ma journée », « qu'est-ce que j'ai aujourd'hui ». Lu tel quel à l'utilisateur.",
        "parameters": {"type": "object", "properties": {}},
    },
]


def build_schema(at_home=None, read_only=None, folders=None):
    """Build the OpenAI tool schema adapted to the current host scope and read-only policy."""
    home_mode = AT_HOME if at_home is None else at_home
    ro = READ_ONLY if read_only is None else read_only
    schema = copy.deepcopy(BASE_SCHEMA)
    if not home_mode:
        where = (setting("folders", "dossiers") or "ses dossiers") if folders is None else (folders or "ses dossiers")
        for tool in schema:
            if tool["name"] == "list_dir":
                tool["parameters"]["properties"]["path"]["description"] = (
                    f"Dossier, relatif à la racine de ses fichiers : {where}."
                )
            elif tool["name"] == "search":
                tool["description"] = "Cherche des fichiers et dossiers par nom (pas dans leur contenu)."
                tool["parameters"]["properties"]["folder"]["description"] = (
                    "Dossier où chercher ; par défaut toute la racine, plus lent."
                )
        if ro:
            schema = [tool for tool in schema if tool["name"] not in WRITING]
    return schema


SCHEMA = build_schema()


class Refusal(Exception):
    """A refusal explained to the model, printed as "REFUS : <reason>"."""


def log_action(text):
    os.makedirs(os.path.dirname(ACTIONS_LOG), exist_ok=True)
    with open(ACTIONS_LOG, "a") as f:
        f.write(time.strftime("%F %T  ") + text + "\n")
