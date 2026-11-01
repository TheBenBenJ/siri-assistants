# spoken_dates.py : dates et heures dictées (vendredi, demain à 9 h 30, 3 novembre), pour ajouter-tache et google-pont.py.
#
# Le calcul se fait ici et non par le modèle : Qwen 9B se trompe de jour.
import datetime
import re
import unicodedata

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
ECARTS = {"aujourd hui": 0, "soir": 0, "matin": 0, "demain": 1, "apres demain": 2}
MOTS_VIDES = {"le", "la", "a", "pour", "ce", "cette", "prochain", "prochaine", "d", "du", "au"}
HEURE = re.compile(r"(?<![\d/-])(\d{1,2})\s*(?:heures?|h|:)\s*(\d{2})?(?!\d)")
MIDI = re.compile(r"(?<![\w-])(midi|minuit)(?!\w)")


def plain(text):
    without_accents = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return without_accents.lower()


def words_of(text):
    return " ".join(w for w in re.sub(r"[^\w/]+", " ", plain(text)).split() if w not in MOTS_VIDES)


def spoken_date(text, today):
    """Date d'une échéance dictée (vendredi, demain, 3 novembre, 3/11, 2026-11-06). ValueError si elle n'est pas comprise."""
    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.date.fromisoformat(text)
    words = words_of(text)
    if words in ECARTS:
        return today + datetime.timedelta(days=ECARTS[words])
    if words == "semaine":  # « la semaine prochaine » : son lundi
        return today + datetime.timedelta(days=7 - today.weekday())
    if words in JOURS:  # le prochain : « vendredi », dit un vendredi, c'est dans une semaine
        return today + datetime.timedelta(days=(JOURS.index(words) - today.weekday() - 1) % 7 + 1)
    found = re.fullmatch(r"(?:\w+ )?(\d{1,2})(?:er)?(?: | ?/ ?)(\w+)(?:(?: | ?/ ?)(\d{4}))?", words)
    if found:
        months = [plain(m) for m in MOIS]
        month = int(found[2]) if found[2].isdigit() else months.index(found[2]) + 1  # ValueError si ce n'est pas un mois
        date = datetime.date(int(found[3] or today.year), month, int(found[1]))
        return date if found[3] or date >= today else date.replace(year=today.year + 1)
    raise ValueError(text)


def spoken_moment(text, today):
    """(date, heure ou None) d'un moment dicté : « vendredi 14h », « demain à 9 h 30 », « 3 novembre », « 18h ». ValueError s'il n'est pas compris."""
    text = plain(text).replace("t", " ", 1) if re.match(r"\d{4}-\d{2}-\d{2}t", plain(text)) else plain(text)
    hour = None
    found = HEURE.search(text)
    noon = MIDI.search(text)
    if found:
        hour = datetime.time(int(found[1]), int(found[2] or 0))  # ValueError si l'heure n'existe pas
        text = text[:found.start()] + " " + text[found.end():]
    elif noon:
        hour = datetime.time(12 if noon[1] == "midi" else 0)
        text = text[:noon.start()] + " " + text[noon.end():]
    rest = text.strip() if re.fullmatch(r"\s*\d{4}-\d{2}-\d{2}\s*", text) else words_of(text)
    return (spoken_date(rest, today) if rest else today), hour


def say_date(date):
    return f"{JOURS[date.weekday()]} {date.day}{'er' if date.day == 1 else ''} {MOIS[date.month - 1]}"


def say_time(time):
    return f"{time.hour} h {time.minute:02d}" if time.minute else f"{time.hour} h"
