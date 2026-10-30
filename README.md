# siri-assistants

Talk to Claude Haiku or a local model by voice with Siri, on Mac and iPhone, in a real back-and-forth conversation. The assistant can read your files; anything destructive waits for a spoken "yes".

Parler à Claude Haiku ou à un modèle local par Siri, sur Mac et iPhone, en vraie conversation. L'assistant peut lire tes fichiers ; toute action destructrice attend un « oui » à voix haute.

## Fonctionnement

iPhone ou Mac → raccourci Siri → SSH via Tailscale → `ask-ssh` → `ask-haiku` ou `ask-local`. La réponse sert d'invite à la question suivante : Siri la lit, puis réécoute. « Merci » ou « stop » met fin à la conversation.

- `ask-haiku` : Claude Code sans fenêtre (`claude -p --bare`) avec une liste fermée d'outils. Si `claude` échoue, repli sur l'API Messages, sans outils. Clé API dans `~/.config/ask-haiku/api-key` (`ask-haiku --set-key`).
- `ask-local` et `outils.py` : un modèle servi par mlx-serve sur `127.0.0.1:11234`, avec des outils de fichiers limités au dossier personnel. Supprimer, déplacer ou écraser reste en attente jusqu'au « oui » du tour suivant.
- `ask-ssh` : seule commande permise aux clés SSH des raccourcis, via `command=` dans `authorized_keys`. La question est transmise au script, jamais exécutée.
- `build-shortcuts.py` : génère et signe les deux raccourcis.

## Installation

Il faut macOS, Tailscale et la session à distance activée.

```sh
ln -s "$PWD"/ask-haiku "$PWD"/ask-local "$PWD"/ask-ssh ~/.local/bin/
mkdir -p ~/.local/share/ask-local && ln -s "$PWD"/outils.py ~/.local/share/ask-local/
ask-haiku --set-key
python3 build-shortcuts.py mon-mac.tailnet.ts.net    # puis ouvrir les .shortcut pour les importer
```

Dans `~/.ssh/authorized_keys`, pour la clé créée par Raccourcis sur chaque appareil :

```
restrict,command="/Users/toi/.local/bin/ask-ssh" ssh-ed25519 AAAA...
```

`ask-haiku` lit et écrit des fichiers à la voix : le contenu d'un fichier reste une donnée pour le prompt, mais cette protection n'est pas absolue. Garde la liste `deny` à jour pour tes dossiers sensibles.
