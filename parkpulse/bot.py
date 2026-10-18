"""WhatsApp-first citizen interface.

The parser handles free text in English, Hinglish, Hindi, Urdu and Dogri, plus
WhatsApp location pins. ``handle_message`` is transport-agnostic: the FastAPI app
wires it to the WhatsApp Cloud API webhook and to the web chat simulator.

Dogri and Urdu reply templates are a first draft and must be reviewed by native
speakers before any public pilot.
"""

from __future__ import annotations

import difflib
import re
import secrets
from dataclasses import dataclass

from .state import LiveState
from .zones import ZONES, ZONES_BY_ID

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
ARABIC = re.compile(r"[؀-ۿ]")
DOGRI_MARKERS = ("कुत्थें", "कित्थें", "कोल", "थाहर", "केह्ड़ी", "डोगरी", "शकायत", " दा ")

T = {
    "en": {
        "menu": "Welcome to ParkPulse Jammu 🅿️\nSend an area name (e.g. Raghunath Bazaar) or share your location pin to find free parking.\nTo report illegal parking, type: report <place>.",
        "header": "🅿️ Parking near {place}:",
        "line": "{i}. {name}: {free} free, ₹{fee}/hr, {walk} min walk",
        "footer": "Reply 1, 2 or 3 for directions.",
        "directions": "Directions to {name}:\n{link}",
        "none": "All nearby parking is full right now. Try again in a few minutes.",
        "unknown": "Sorry, I didn't catch the place. Type an area name (e.g. Gandhi Nagar) or share your location pin.",
        "report": "Thank you! Complaint registered (ID {id}). Traffic police have been alerted.",
        "trend": {"filling": "filling up", "emptying": "freeing up", "steady": "steady"},
        "your_location": "you",
    },
    "hi": {
        "menu": "ParkPulse जम्मू में आपका स्वागत है 🅿️\nइलाके का नाम लिखें (जैसे: रघुनाथ बाजार) या अपनी लोकेशन भेजें।\nगलत पार्किंग की शिकायत के लिए लिखें: शिकायत <जगह>",
        "header": "🅿️ {place} के पास पार्किंग:",
        "line": "{i}. {name}: {free} जगह खाली, ₹{fee}/घंटा, पैदल {walk} मिनट",
        "footer": "रास्ते के लिए 1, 2 या 3 लिखें।",
        "directions": "{name} का रास्ता:\n{link}",
        "none": "अभी आस-पास की सारी पार्किंग भरी है। कुछ मिनट बाद फिर कोशिश करें।",
        "unknown": "माफ़ कीजिए, जगह समझ नहीं आई। इलाके का नाम लिखें (जैसे: गांधी नगर) या अपनी लोकेशन भेजें।",
        "report": "धन्यवाद! शिकायत दर्ज हो गई (ID {id})। ट्रैफिक पुलिस को सूचना भेज दी गई है।",
        "trend": {"filling": "भर रही है", "emptying": "खाली हो रही है", "steady": "स्थिर"},
        "your_location": "आपकी लोकेशन",
    },
    "ur": {
        "menu": "ParkPulse جموں میں خوش آمدید 🅿️\nعلاقے کا نام لکھیں یا اپنی لوکیشن بھیجیں۔\nغلط پارکنگ کی شکایت کے لیے لکھیں: شکایت <جگہ>",
        "header": "🅿️ {place} کے قریب پارکنگ:",
        "line": "{i}. {name}: {free} جگہیں خالی، ₹{fee} فی گھنٹہ، پیدل {walk} منٹ",
        "footer": "راستے کے لیے 1، 2 یا 3 لکھیں۔",
        "directions": "{name} کا راستہ:\n{link}",
        "none": "ابھی قریب کی ساری پارکنگ بھری ہے۔ چند منٹ بعد دوبارہ کوشش کریں۔",
        "unknown": "معاف کیجیے، جگہ سمجھ نہیں آئی۔ علاقے کا نام لکھیں یا اپنی لوکیشن بھیجیں۔",
        "report": "شکریہ! شکایت درج ہو گئی (ID {id})۔ ٹریفک پولیس کو اطلاع دے دی گئی ہے۔",
        "trend": {"filling": "بھر رہی ہے", "emptying": "خالی ہو رہی ہے", "steady": "مستحکم"},
        "your_location": "آپ کی لوکیشن",
    },
    # NEEDS NATIVE REVIEW: first-draft Dogri strings.
    "doi": {
        "menu": "ParkPulse जम्मू च तुंदा स्वागत ऐ 🅿️\nइलाके दा नां लिखो (जियां: रघुनाथ बजार) जां अपनी लोकेशन भेजो।\nगलत पार्किंग दी शकायत आस्तै लिखो: शकायत <थाहर>",
        "header": "🅿️ {place} दे कोल पार्किंग:",
        "line": "{i}. {name}: {free} थाहरां खाली, ₹{fee}/घैंटा, पैदल {walk} मिंट",
        "footer": "रस्ते आस्तै 1, 2 जां 3 लिखो।",
        "directions": "{name} दा रस्ता:\n{link}",
        "none": "इस बेलै कोल दी सारी पार्किंग भरोची दी ऐ। किश मिंटें बाद फ्ही कोशश करो।",
        "unknown": "माफ करो, थाहर समझ नेईं आई। इलाके दा नां लिखो जां अपनी लोकेशन भेजो।",
        "report": "शुक्रिया! शकायत दर्ज होई गेई (ID {id})। ट्रैफिक पुलिस गी खबर देई दित्ती गेई ऐ।",
        "trend": {"filling": "भरोआ दी ऐ", "emptying": "खाली होआ दी ऐ", "steady": "स्थिर"},
        "your_location": "तुंदी लोकेशन",
    },
}

REPORT_WORDS = ("report", "complaint", "illegal", "shikayat", "शिकायत", "शकायत", "شکایت")
GREETING_WORDS = ("hi", "hello", "help", "menu", "start", "namaste", "नमस्ते", "मदद", "سلام", "مدد", "salaam")


@dataclass
class Reply:
    text: str
    lang: str
    intent: str
    data: dict | None = None


def detect_language(text: str) -> str:
    if ARABIC.search(text):
        return "ur"
    if DEVANAGARI.search(text):
        return "doi" if any(m in text for m in DOGRI_MARKERS) else "hi"
    return "en"


def match_zone(text: str):
    low = text.casefold()
    best, best_score = None, 0.0
    for z in ZONES:
        for alias in (z.name.casefold(),) + tuple(a.casefold() for a in z.aliases):
            if alias in low:
                score = 1.0 + len(alias) / 100
            else:
                score = max((difflib.SequenceMatcher(None, alias, tok).ratio()
                             for tok in _ngrams(low, len(alias.split()))), default=0.0)
            if score > best_score:
                best, best_score = z, score
    return best if best_score >= 0.82 else None


def _ngrams(text: str, n: int) -> list[str]:
    toks = re.findall(r"[\wऀ-ॿ؀-ۿ]+", text)
    n = max(1, n)
    return [" ".join(toks[i:i + n]) for i in range(max(1, len(toks) - n + 1))]


def _format_options(state: LiveState, lang: str, place: str, lat: float, lon: float, exclude_full: bool = True) -> Reply:
    t = T[lang]
    rows = state.nearest(lat, lon, limit=3, min_free=1 if exclude_full else 0)
    if not rows:
        return Reply(t["none"], lang, "find", {"options": []})
    lines = [t["header"].format(place=place)]
    for i, r in enumerate(rows, 1):
        line = t["line"].format(i=i, name=r["name"], free=r["free"], fee=r["hourly_fee"], walk=r["walk_min"])
        if r.get("trend_3h"):
            line += f"  ({t['trend'][r['trend_3h']]})"
        lines.append(line)
    lines.append(t["footer"])
    return Reply("\n".join(lines), lang, "find", {"options": rows})


CHOICE_DIGITS = {"1": 0, "2": 1, "3": 2, "१": 0, "२": 1, "३": 2, "۱": 0, "۲": 1, "۳": 2, "١": 0, "٢": 1, "٣": 2}


def handle_message(state: LiveState, text: str = "", location: tuple[float, float] | None = None,
                   lang: str | None = None, session: dict | None = None) -> Reply:
    """Answer one inbound message. ``session`` is a per-user dict kept by the caller
    (keyed by WhatsApp number) so a follow-up "2" can return directions."""
    text = (text or "").strip()
    session = session if session is not None else {}
    lang = lang or (session.get("lang") if text in CHOICE_DIGITS else None) or detect_language(text)
    t = T[lang]

    if text in CHOICE_DIGITS and session.get("options"):
        idx = CHOICE_DIGITS[text]
        opts = session["options"]
        if idx < len(opts):
            o = opts[idx]
            return Reply(t["directions"].format(name=o["name"], link=o["directions"]), lang, "directions", {"option": o})

    reply = _route(state, text, location, lang, t)
    if reply.intent == "find" and reply.data:
        session["options"] = reply.data.get("options", [])
        session["lang"] = lang
    return reply


def _route(state: LiveState, text: str, location, lang: str, t: dict) -> Reply:
    if location is not None:
        return _format_options(state, lang, t["your_location"], *location)

    low = text.casefold()
    if any(w in low for w in REPORT_WORDS):
        zone = match_zone(text)
        ticket = "R" + secrets.token_hex(3).upper()
        data = {"ticket": ticket, "zone_id": zone.id if zone else None, "raw": text}
        return Reply(t["report"].format(id=ticket), lang, "report", data)

    if not text or low in GREETING_WORDS or low.split()[0] in GREETING_WORDS:
        return Reply(t["menu"], lang, "menu")

    zone = match_zone(text)
    if zone:
        place = next((a for a in zone.aliases if a.casefold() in low), zone.name)
        return _format_options(state, lang, place if lang != "en" else zone.name, zone.lat, zone.lon)
    return Reply(t["unknown"], lang, "unknown")


def zone_name(zone_id: str) -> str:
    return ZONES_BY_ID[zone_id].name
