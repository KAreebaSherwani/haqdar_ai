"""Missing-information detector.

If a complaint is too thin to answer safely (e.g. just "Police fined me"),
HaqDar does NOT guess — it returns targeted clarifying questions in Urdu.
Lightweight heuristic by design: fast, deterministic, no extra AI call.

Covers all 10 verified civic domains. Completeness check is two-pronged:
a hard minimum word count AND a check for at least one concrete detail
(place / date / organisation), so a short-but-vague complaint still gets
clarifying questions.
"""

import re

# Domain keyword map (Roman Urdu + Urdu script + English) — all 10 domains
_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "police": {"police", "پولیس", "fine", "jurmana", "جرمانہ", "challan", "چالان", "thana", "تھانہ"},
    "healthcare": {"hospital", "ہسپتال", "ilaj", "علاج", "doctor", "ڈاکٹر", "emergency", "ایمرجنسی", "mareez", "مریض"},
    "utility": {"wapda", "واپڈا", "bijli", "بجلی", "bill", "بل", "gas", "گیس", "meter", "میٹر", "sui", "سوئی", "lesco", "iesco", "fesco", "pesco", "hesco", "gepco", "mepco", "k-electric"},
    "labour": {"tankhwah", "تنخواہ", "salary", "wage", "ujrat", "اجرت", "malik", "مالک", "mazdoor", "مزدور", "factory", "فیکٹری"},
    "education": {"school", "سکول", "fees", "فیس", "fee", "college", "کالج", "admission", "داخلہ", "university", "یونیورسٹی"},
    "women": {"harassment", "ہراسانی", "harass", "تنگ", "khatoon", "خاتون", "workplace", "office", "دفتر", "boss", "باس", "supervisor", "سپروائزر", "sexual", "جنسی", "misbehaviour", "بدتمیزی", "zyadti", "زیادتی"},
    "consumer": {"dukan", "دکان", "qeemat", "قیمت", "price", "kharab", "خراب", "refund", "shopkeeper", "دکاندار"},
    "traffic": {"traffic", "ٹریفک", "warden", "وارڈن", "gari", "گاڑی", "license", "لائسنس", "challan", "چالان"},
    "rti": {"rti", "information", "record", "darkhwast", "درخواست", "maloomat", "معلومات", "transparency", "آر ٹی آئی", "حق معلومات", "اطلاعات", "ریکارڈ"},
    "municipal": {"municipal", "municipality", "water", "sewerage", "wasa", "واسا", "garbage", "kachra", "کچرا", "safai", "صفائی", "sarak", "سڑک", "nala", "نالہ", "street", "drainage", "naliyan", "نالیاں", "streetlight", "سٹریٹ لائٹ", "park", "پارک"},
}

_QUESTIONS: dict[str, list[str]] = {
    "police": [
        "یہ واقعہ کس شہر یا ضلع میں پیش آیا؟",
        "کیا آپ کو کوئی رسید یا چالان دیا گیا؟",
        "واقعہ کب پیش آیا (تاریخ یا اندازاً)؟",
    ],
    "healthcare": [
        "کس ہسپتال یا کلینک میں یہ مسئلہ پیش آیا؟",
        "کیا یہ ایمرجنسی کی صورتحال تھی؟",
        "واقعہ کب پیش آیا？",
    ],
    "utility": [
        "کون سا ادارہ ہے (بجلی، گیس، پانی)؟",
        "بل کی رقم کتنی ہے اور کیا غلط لگ رہی ہے؟",
        "کیا آپ نے ادارے سے رابطہ کیا؟",
    ],
    "labour": [
        "آپ کہاں کام کرتے ہیں (ادارہ/فیکٹری/دکان)؟",
        "کتنے عرصے کی تنخواہ نہیں ملی؟",
        "کیا آپ کے پاس تقرری نامہ یا ملازمت کا ثبوت ہے؟",
    ],
    "education": [
        "کس سکول، کالج یا یونیورسٹی کا معاملہ ہے؟",
        "کیا یہ فیس، داخلے یا کسی اور حق کا مسئلہ ہے؟",
        "کیا آپ نے ادارے کی انتظامیہ سے رابطہ کیا؟",
    ],
    "women": [
        "یہ معاملہ کہاں پیش آیا (کام کی جگہ/ادارہ)؟",
        "کیا ادارے میں کوئی شکایتی کمیٹی موجود ہے؟",
        "کیا آپ کے پاس کوئی ثبوت یا گواہ موجود ہے؟",
    ],
    "consumer": [
        "کس دکان یا ادارے سے معاملہ ہوا؟",
        "کیا آپ سے مقررہ قیمت سے زیادہ وصول کیا گیا یا چیز خراب نکلی؟",
        "کیا آپ کے پاس رسید یا خریداری کا ثبوت ہے؟",
    ],
    "traffic": [
        "یہ واقعہ کس شہر یا ضلع میں پیش آیا؟",
        "کیا چالان پر خلاف ورزی کی تفصیل درج تھی اور رسید دی گئی؟",
        "واقعہ کب پیش آیا؟",
    ],
    "rti": [
        "آپ نے کس ادارے سے معلومات مانگی تھیں؟",
        "کیا آپ نے تحریری درخواست جمع کروائی تھی؟",
        "درخواست جمع کروائے کتنے دن گزر چکے ہیں؟",
    ],
    "municipal": [
        "مسئلہ کس علاقے یا محلے میں ہے؟",
        "کیا یہ صفائی، پانی، سیوریج یا سڑک کا مسئلہ ہے؟",
        "کیا آپ نے متعلقہ بلدیاتی ادارے کو پہلے اطلاع دی تھی؟",
    ],
    "general": [
        "براہ کرم بتائیں کہ کیا ہوا، کہاں ہوا، اور کب ہوا؟",
        "اس میں کون سا ادارہ یا شخص ملوث ہے؟",
        "کیا آپ کے پاس کوئی ثبوت (رسید، تصویر، گواہ) موجود ہے؟",
    ],
}

_MIN_WORDS = 6

# Known Punjab districts (Roman + Urdu) → canonical Urdu name, for auto-extraction.
# Lets the heatmap fill and the letter personalize even if the user skips the dropdown.
_DISTRICTS: dict[str, str] = {
    "rawalpindi": "راولپنڈی", "راولپنڈی": "راولپنڈی", "pindi": "راولپنڈی",
    "lahore": "لاہور", "لاہور": "لاہور",
    "islamabad": "اسلام آباد", "اسلام آباد": "اسلام آباد",
    "faisalabad": "فیصل آباد", "فیصل آباد": "فیصل آباد",
    "multan": "ملتان", "ملتان": "ملتان",
    "gujranwala": "گوجرانوالہ", "گوجرانوالہ": "گوجرانوالہ",
    "sialkot": "سیالکوٹ", "سیالکوٹ": "سیالکوٹ",
    "bahawalpur": "بہاولپور", "بہاولپور": "بہاولپور",
    "sargodha": "سرگودھا", "سرگودھا": "سرگودھا",
    "sahiwal": "ساہیوال", "ساہیوال": "ساہیوال",
    "sheikhupura": "شیخوپورہ", "شیخوپورہ": "شیخوپورہ",
    "jhang": "جھنگ", "جھنگ": "جھنگ",
    "kasur": "قصور", "قصور": "قصور",
    "okara": "اوکاڑہ", "اوکاڑہ": "اوکاڑہ",
    "karachi": "کراچی", "کراچی": "کراچی",
    "peshawar": "پشاور", "پشاور": "پشاور",
    "quetta": "کوئٹہ", "کوئٹہ": "کوئٹہ",
}

# Signals that a complaint carries at least one concrete detail
_PLACE_HINTS = {
    "mein", "میں", "shehar", "شہر", "zila", "ضلع", "ilaqa", "علاقہ", "muhalla", "محلہ",
    "rawalpindi", "راولپنڈی", "lahore", "لاہور", "islamabad", "اسلام آباد", "karachi", "کراچی",
    "faisalabad", "فیصل", "multan", "ملتان", "gujranwala", "گوجرانوالہ", "office", "دفتر", "address",
}
_TIME_HINTS = {
    "kal", "کل", "aaj", "آج", "subah", "صبح", "shaam", "شام", "raat", "رات",
    "tareekh", "تاریخ", "month", "mahine", "مہینے", "din", "دن", "hafta", "ہفتہ",
    "2024", "2025", "2026", "january", "jun", "جون", "july",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", text)


def extract_district(text: str) -> str | None:
    """Auto-detect a Punjab/PK district mentioned in the complaint text.

    Returns the canonical Urdu district name, or None. Used to fill the heatmap
    and personalize the letter when the user hasn't picked the dropdown.
    """
    lowered = text.lower()
    tokens = {w.lower() for w in _words(text)}
    for key, canonical in _DISTRICTS.items():
        if key in tokens or key in lowered:
            return canonical
    return None


def detect_domain(text: str) -> str:
    tokens = {w.lower() for w in _words(text)}
    best, best_hits = "general", 0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if hits := len(tokens & keywords):
            if hits > best_hits:
                best, best_hits = domain, hits
    return best


def _has_concrete_detail(complaint: str, tokens: set[str]) -> bool:
    """True if the complaint mentions a place or a time/date.

    A bare amount like "500 rupay" is NOT a location, so a standalone number
    does not count. We only treat numbers as location when paired with an
    address word (sector/block/house/road), e.g. "Sector G-9", "block 4".
    """
    has_place = bool(tokens & _PLACE_HINTS)
    has_time = bool(tokens & _TIME_HINTS)
    has_address = bool(
        re.search(r"(sector|block|house|street|road|سیکٹر|بلاک|مکان|گلی|سڑک)\s*[-#]?\s*\w*\d", complaint, re.I)
    )
    return has_place or has_time or has_address


def check(complaint: str) -> tuple[bool, str, list[str], str | None]:
    """Return (needs_more_info, detected_domain, questions, extracted_district).

    Asks for more info when the complaint is either too short OR lacks any
    concrete detail (no place and no time/date), so short-but-vague complaints
    still get clarifying questions instead of an assumed answer.
    """
    words = _words(complaint)
    domain = detect_domain(complaint)
    tokens = {w.lower() for w in words}

    too_short = len(words) < _MIN_WORDS
    too_vague = (len(words) < 12) and not _has_concrete_detail(complaint, tokens)
    
    # Extract the district natively to pass along to the response pipeline
    extracted_district = extract_district(complaint)

    if too_short or too_vague:
        return True, domain, _QUESTIONS.get(domain, _QUESTIONS["general"]), extracted_district
        
    return False, domain, [], extracted_district