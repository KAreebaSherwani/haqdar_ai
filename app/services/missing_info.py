"""Missing-information detector.

If a complaint is too thin to answer safely (e.g. just "Police fined me"),
HaqDar does NOT guess — it returns targeted clarifying questions in Urdu.
Lightweight heuristic by design: fast, deterministic, no extra AI call.
"""

import re

# Domain keyword map (Roman Urdu + Urdu script + English)
_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "police": {"police", "پولیس", "fine", "jurmana", "جرمانہ", "challan", "چالان", "thana", "تھانہ"},
    "healthcare": {"hospital", "ہسپتال", "ilaj", "علاج", "doctor", "ڈاکٹر", "emergency", "ایمرجنسی"},
    "utility": {"wapda", "واپڈا", "bijli", "بجلی", "bill", "بل", "gas", "گیس", "meter", "میٹر"},
    "labour": {"tankhwah", "تنخواہ", "salary", "wage", "malik", "مالک", "mazdoor", "مزدور"},
    "education": {"school", "سکول", "fees", "فیس", "college", "کالج", "admission", "داخلہ"},
    "women": {"harassment", "ہراسانی", "harass", "تنگ"},
    "consumer": {"dukan", "دکان", "qeemat", "قیمت", "price", "kharab", "خراب", "refund"},
    "traffic": {"traffic", "ٹریفک", "warden", "وارڈن", "gari", "گاڑی", "license", "لائسنس"},
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
        "واقعہ کب پیش آیا؟",
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
    "general": [
        "براہ کرم بتائیں کہ کیا ہوا، کہاں ہوا، اور کب ہوا؟",
        "اس میں کون سا ادارہ یا شخص ملوث ہے؟",
        "کیا آپ کے پاس کوئی ثبوت (رسید، تصویر، گواہ) موجود ہے؟",
    ],
}

_MIN_WORDS = 5


def _words(text: str) -> list[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", text)


def detect_domain(text: str) -> str:
    tokens = {w.lower() for w in _words(text)}
    best, best_hits = "general", 0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = len(tokens & keywords)
        if hits > best_hits:
            best, best_hits = domain, hits
    return best


def check(complaint: str) -> tuple[bool, str, list[str]]:
    """Return (needs_more_info, detected_domain, questions)."""
    domain = detect_domain(complaint)
    if len(_words(complaint)) < _MIN_WORDS:
        return True, domain, _QUESTIONS.get(domain, _QUESTIONS["general"])
    return False, domain, []
