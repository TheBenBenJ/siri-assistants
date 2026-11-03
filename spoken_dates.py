# spoken_dates.py: dates and times as the user says them in French ("vendredi", "demain à 9 h 30", "3 novembre"),
# for ajouter-tache and the Google bridge.
#
# Dates are computed here, never by the model: Qwen 9B gets the day wrong (it once put "vendredi" on a Saturday).
# The models pass dates on exactly as they were said. Everything said back is French, as it is read aloud.
import datetime
import re
import unicodedata

WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAY_OFFSETS = {"aujourd hui": 0, "soir": 0, "matin": 0, "demain": 1, "apres demain": 2}
FILLER_WORDS = {"le", "la", "a", "pour", "ce", "cette", "prochain", "prochaine", "d", "du", "au"}
CLOCK_TIME = re.compile(r"(?<![\d/-])(\d{1,2})\s*(?:heures?|h|:)\s*(\d{2})?(?!\d)")
NOON_OR_MIDNIGHT = re.compile(r"(?<![\w-])(midi|minuit)(?!\w)")


def plain(text):
    without_accents = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return without_accents.lower()


def words_of(text):
    return " ".join(w for w in re.sub(r"[^\w/]+", " ", plain(text)).split() if w not in FILLER_WORDS)


def spoken_date(text, today):
    """Date of a spoken due date (vendredi, demain, 3 novembre, 3/11, 2026-11-06). ValueError if it is not understood."""
    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.date.fromisoformat(text)
    words = words_of(text)
    if words in DAY_OFFSETS:
        return today + datetime.timedelta(days=DAY_OFFSETS[words])
    if words == "semaine":  # "la semaine prochaine": its Monday
        return today + datetime.timedelta(days=7 - today.weekday())
    if words in WEEKDAYS:  # the next one: "vendredi" said on a Friday means a week later
        return today + datetime.timedelta(days=(WEEKDAYS.index(words) - today.weekday() - 1) % 7 + 1)
    found = re.fullmatch(r"(?:\w+ )?(\d{1,2})(?:er)?(?: | ?/ ?)(\w+)(?:(?: | ?/ ?)(\d{4}))?", words)
    if found:
        months = [plain(m) for m in MONTHS]
        month = int(found[2]) if found[2].isdigit() else months.index(found[2]) + 1  # ValueError if it is not a month
        date = datetime.date(int(found[3] or today.year), month, int(found[1]))
        return date if found[3] or date >= today else date.replace(year=today.year + 1)
    raise ValueError(text)


def spoken_moment(text, today):
    """(date, time or None) of a spoken moment: "vendredi 14h", "demain à 9 h 30", "3 novembre", "18h". ValueError if it is not understood."""
    text = plain(text).replace("t", " ", 1) if re.match(r"\d{4}-\d{2}-\d{2}t", plain(text)) else plain(text)
    hour = None
    found = CLOCK_TIME.search(text)
    noon = NOON_OR_MIDNIGHT.search(text)
    if found:
        hour = datetime.time(int(found[1]), int(found[2] or 0))  # ValueError if the time does not exist
        text = text[:found.start()] + " " + text[found.end():]
    elif noon:
        hour = datetime.time(12 if noon[1] == "midi" else 0)
        text = text[:noon.start()] + " " + text[noon.end():]
    rest = text.strip() if re.fullmatch(r"\s*\d{4}-\d{2}-\d{2}\s*", text) else words_of(text)
    return (spoken_date(rest, today) if rest else today), hour


def say_date(date):
    """The date as it is read aloud: "vendredi 6 novembre", "dimanche 1er novembre"."""
    return f"{WEEKDAYS[date.weekday()]} {date.day}{'er' if date.day == 1 else ''} {MONTHS[date.month - 1]}"


def say_time(time):
    """The time as it is read aloud: "9 h", "14 h 30"."""
    return f"{time.hour} h {time.minute:02d}" if time.minute else f"{time.hour} h"
