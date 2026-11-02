# siri-assistants

Talk to Claude Haiku or a local model by voice with Siri, on Mac and iPhone, in a real back-and-forth conversation. The assistant can read your files; anything destructive waits for a spoken "yes".

Parler à Claude Haiku ou à un modèle local par Siri, sur Mac et iPhone, en vraie conversation. L'assistant peut lire tes fichiers ; toute action destructrice attend un « oui » à voix haute.

## Fonctionnement

iPhone ou Mac → raccourci Siri → SSH via Tailscale → `ask-ssh` → `ask-haiku` ou `ask-local`. La réponse sert d'invite à la question suivante : Siri la lit, puis réécoute. « Merci » ou « stop » met fin à la conversation.

- `ask-haiku` : Claude Code sans fenêtre (`claude -p --bare`) avec une liste fermée d'outils. Si `claude` échoue, repli sur l'API Messages, sans outils. Clé API dans `~/.config/ask-haiku/api-key` (`ask-haiku --set-key`).
- `ask-local` et `outils.py` : un modèle servi par mlx-serve sur `127.0.0.1:11234`, avec des outils de fichiers limités au dossier personnel. Supprimer, déplacer ou écraser reste en attente jusqu'au « oui » du tour suivant.
- `ajouter-tache` : donne aux deux assistants de quoi noter une tâche à la voix, avec une date si besoin. Elle est envoyée à un serveur local sur `127.0.0.1:8765` (`POST /taches`, en-tête `X-Dashboard: 1`, `{"action": "ajouter", "assistant": true, "libelle", "echeance"}`), ici un dashboard personnel qui la recopie dans Google Tasks. Le serveur garde seul le jeton Google, dans le trousseau, inaccessible par SSH. Adapte `ENDPOINT` à ton propre service.
- `google-pont.py`, `google` : le compte Google (Gmail, Agenda, Drive, Contacts, Tasks, et les notes Keep copiées par le dashboard). Le pont tourne dans la session de l'utilisateur, sur `127.0.0.1:8766`, et garde seul le jeton. Sur un serveur Linux, il tourne aussi en service systemd : le jeton lui arrive alors chiffré, par `LoadCredentialEncrypted=google-pont`. Lire est immédiat. Envoyer ou modifier n'est qu'une proposition gardée dans le pont : le script de l'assistant la lit à voix haute, et seul un « oui » au tour suivant l'exécute. Le modèle ne peut ni la confirmer ni la maquiller, donc le contenu d'un mail ne peut rien envoyer tout seul.
- `recap` : donne aux deux assistants le récap du jour, un petit JSON posé dans iCloud Drive (`05 Assistants/Recap du jour.json`), ici écrit par le dashboard personnel. Il faut au moins `date`, `genere_a` et `a_dire`, le texte lu à voix haute ; les autres champs servent aux questions de suite de Haiku. Pour le modèle local, c'est le script qui lit `a_dire`, sans lui laisser le reformuler. Un récap périmé est annoncé comme tel. Adapte `FICHIER` à ton propre service.
- `ask-ssh` : seule commande permise aux clés SSH des raccourcis, via `command=` dans `authorized_keys`. La question est transmise au script, jamais exécutée.
- `build-shortcuts.py` : génère et signe les deux raccourcis.

## Installation

Il faut macOS, Tailscale et la session à distance activée.

```sh
ln -s "$PWD"/ask-haiku "$PWD"/ask-local "$PWD"/ask-ssh "$PWD"/ajouter-tache "$PWD"/google "$PWD"/recap ~/.local/bin/
mkdir -p ~/.local/share/ask-local && ln -s "$PWD"/outils.py ~/.local/share/ask-local/
ask-haiku --set-key
./google-pont.py --autoriser    # il faut un client OAuth « Application de bureau », application publiée sinon le jeton expire en 7 jours
./google-pont.py --installer    # agent launchd
python3 build-shortcuts.py mon-mac.tailnet.ts.net    # puis ouvrir les .shortcut pour les importer
```

Dans `~/.ssh/authorized_keys`, pour la clé créée par Raccourcis sur chaque appareil :

```
restrict,command="/Users/toi/.local/bin/ask-ssh" ssh-ed25519 AAAA...
```

`ask-haiku` lit et écrit des fichiers à la voix : le contenu d'un fichier reste une donnée pour le prompt, mais cette protection n'est pas absolue. Garde la liste `deny` à jour pour tes dossiers sensibles.
