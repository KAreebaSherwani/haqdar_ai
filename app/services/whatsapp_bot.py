"""WhatsApp bot — a conversational front door to the existing HaqDar pipeline.

Design principles (locked):
- Reuses analyze_complaint(); adds NO new AI logic.
- Asks at most ONE clarifying question, and only when the law is genuinely
  ambiguous. Otherwise it proceeds and leaves blanks on the letter.
- Never crashes: any non-menu message is treated as a new complaint; menu
  matching is loose; unknown input gets a gentle re-prompt.
- Scramble-proof formatting: numbers lead their own lines; Urdu lines stay pure
  Urdu, English lines stay pure English.
- Privacy: never asks for name / CNIC / address.

State is per-phone-number, in memory (fine for a demo). Each turn returns the
text the webhook should send back.
"""

from __future__ import annotations

import logging
import re
import time

from app.services.analysis_service import analyze_complaint

logger = logging.getLogger("haqdar.whatsapp")

# ---- In-memory conversation state (per phone number) ------------------------
# { phone: {"stage": str, "language": "Urdu"|"English", "complaint": str,
#           "pending": dict, "updated": float} }
_SESSIONS: dict[str, dict] = {}
_SESSION_TTL = 60 * 60 * 6  # 6h; stale sessions reset cleanly


def _now() -> float:
    return time.time()


def _session(phone: str) -> dict:
    s = _SESSIONS.get(phone)
    if s is None or (_now() - s.get("updated", 0)) > _SESSION_TTL:
        s = {"stage": "new", "language": "Urdu", "complaint": "", "pending": {}, "updated": _now()}
        _SESSIONS[phone] = s
    return s


def _save(phone: str, **kw) -> None:
    s = _session(phone)
    s.update(kw)
    s["updated"] = _now()


# ---- Language detection -----------------------------------------------------
_ROMAN_URDU_MARKERS = {
    "ne", "ko", "mein", "nahi", "nahin", "kiya", "hai", "hain", "mujhe", "mera",
    "meri", "ka", "ki", "ke", "wala", "kar", "raha", "rahi", "tha", "thi", "aur",
    "se", "par", "bina", "tankhwah", "malik", "malkan", "jurmana", "shikayat",
    "police", "thana", "paisa", "paise", "din", "mahine",
}


def detect_language(text: str) -> str:
    """Detect the user's language for guidance output.

    - Arabic-script characters -> Urdu.
    - Latin text with >=2 Roman-Urdu markers -> Urdu (the user is an Urdu speaker
      typing in Roman script; they want Urdu guidance).
    - Otherwise -> English.
    """
    if any("\u0600" <= ch <= "\u06FF" for ch in text):
        return "Urdu"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & _ROMAN_URDU_MARKERS) >= 2:
        return "Urdu"
    return "English"


# ---- Greeting (the only bilingual message) ----------------------------------
GREETING = (
    "السلام علیکم 👋\n"
    "آپ بالکل درست جگہ پہنچے ہیں۔\n"
    "اپنا مسئلہ کسی بھی زبان میں لکھیں، یا وائس نوٹ بھیجیں۔\n"
    "ہم آپ کے ساتھ ہیں۔\n"
    "\n"
    "\u200eWelcome to HaqDar AI 👋\n"
    "\u200eYou've come to the right place.\n"
    "\u200eShare your problem in any language, or send a voice note.\n"
    "\u200eWe're with you."
)

# ---- Fixed UI lines, per language -------------------------------------------
def _ack(lang: str) -> str:
    if lang == "Urdu":
        return "آپ کی بات ہم تک پہنچ گئی ہے۔\nفکر نہ کریں — ہم آپ کے لیے راستہ تلاش کر رہے ہیں..."
    return "We've received your concern.\nDon't worry — we're finding your way forward..."


def _empty_prompt(lang: str) -> str:
    if lang == "Urdu":
        return ("براہ کرم اپنا مسئلہ مختصر بیان کریں۔\n"
                "مثال: مالکن نے دو مہینے کی تنخواہ روک لی۔")
    return ("Please describe your problem briefly.\n"
            "Example: My employer withheld two months of my salary.")


def _pdf_menu(lang: str) -> str:
    if lang == "Urdu":
        head = "*کیا آپ کو باقاعدہ درخواست چاہیے؟*\nنیچے نمبر لکھ کر بھیجیں 👇"
        no = "No / نہیں"
    else:
        head = "*Would you like a formal petition?*\nReply with the number 👇"
        no = "No"
    # Each option line is wrapped in a Left-to-Right mark (\u200e) so the
    # number stays glued to the LEFT of the label even inside an RTL message.
    return (
        f"{head}\n\n"
        f"\u200e1\u20e3  Urdu PDF\n"
        f"\u200e2\u20e3  English PDF\n"
        f"\u200e3\u20e3  {no}"
    )


def _menu_fallback(lang: str) -> str:
    if lang == "Urdu":
        return "معذرت، سمجھ نہیں آیا۔\nاردو کے لیے 1، انگریزی کے لیے 2، یا منع کے لیے 3 بھیجیں۔"
    return "Sorry, I didn't catch that.\nReply 1 for Urdu PDF, 2 for English, or 3 for No."


def _fill_note(lang: str, fields: list[str]) -> str:
    items = "، ".join(fields) if lang == "Urdu" else ", ".join(fields)
    if lang == "Urdu":
        return (f"📝 پرنٹ کرنے کے بعد یہ خانے پُر کریں:\n{items}\n\n"
                "یہ درخواست آپ کی آواز ہے۔ آپ یہ کر سکتے ہیں۔ 🤝")
    return (f"📝 After printing, fill in:\n{items}\n\n"
            "This petition is your voice. You can do this. 🤝")


# ---- Guidance formatter (the AI answer, user's language) --------------------
def _format_guidance(resp, lang: str) -> str:
    """resp is an AnalyzeResponse. Build a scannable WhatsApp message."""
    if lang == "Urdu":
        intro = "*آپ کے پاس مضبوط قانونی حق موجود ہے۔*"
        L = ("📋 *آپ کا حق*", "⚖️ *متعلقہ قانون*", "🏛️ *کہاں رجوع کریں*", "✅ *اگلے اقدامات*")
    else:
        intro = "*You have a strong legal right here.*"
        L = ("📋 *Your Right*", "⚖️ *The Law*", "🏛️ *Where to Go*", "✅ *Next Steps*")
    steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(resp.next_steps or []))
    parts = [
        intro, "",
        f"{L[0]}\n{resp.citizen_rights}", "",
        f"{L[1]}\n{resp.law_reference}", "",
        f"{L[2]}\n{resp.responsible_authority}", "",
        f"{L[3]}\n{steps}", "",
        f"🔖 Reference: {resp.reference_id}",
    ]
    return "\n".join(parts)


# ---- Menu answer parsing (loose) --------------------------------------------
def _parse_menu(text: str) -> str | None:
    """Return 'urdu' | 'english' | 'no' | None."""
    t = text.strip().lower()
    # normalize Urdu/Arabic digits
    digits = {"۱": "1", "۲": "2", "۳": "3", "١": "1", "٢": "2", "٣": "3"}
    for u, e in digits.items():
        t = t.replace(u, e)
    if t in {"1", "1️⃣"} or "urdu" in t or "اردو" in t:
        return "urdu"
    if t in {"2", "2️⃣"} or "english" in t or "انگریزی" in t or "انگلش" in t:
        return "english"
    if t in {"3", "3️⃣"} or t in {"no", "nahi", "nahin"} or "نہیں" in t or "منع" in t:
        return "no"
    return None


def _looks_like_complaint(text: str) -> bool:
    """A menu reply is short; a complaint has real words. If the user sends a
    sentence instead of 1/2/3, treat it as a new complaint."""
    return len(re.findall(r"[\w\u0600-\u06FF]+", text)) >= 4


# ---- Main entry: handle one inbound message ---------------------------------
async def handle_message(phone: str, text: str) -> str:
    """Process one WhatsApp message; return the reply text. Never raises."""
    try:
        text = (text or "").strip()
        s = _session(phone)

        # Greeting triggers / empty
        low = text.lower()
        if not text:
            return _empty_prompt(s["language"])
        # No real words (lone emoji, punctuation, single char) -> not a complaint.
        # Only short-circuit when NOT mid-menu (a 1-char menu reply is valid there).
        if s["stage"] != "awaiting_pdf_choice" and len(re.findall(r"[\w\u0600-\u06FF]{2,}", text)) == 0:
            return _empty_prompt(s["language"])
        if s["stage"] == "new" and low in {"hi", "hello", "hey", "start", "salam",
                                           "asalam o alaikum", "السلام علیکم", "اسلام علیکم",
                                           "assalamualaikum", "test"}:
            _save(phone, stage="greeted")
            return GREETING

        # --- Stage: awaiting PDF choice ---------------------------------------
        if s["stage"] == "awaiting_pdf_choice":
            choice = _parse_menu(text)
            if choice == "no":
                _save(phone, stage="done")
                return ("شکریہ! کسی بھی وقت دوبارہ رابطہ کریں۔" if s["language"] == "Urdu"
                        else "Thank you! Reach out any time.")
            if choice in {"urdu", "english"}:
                letter_lang = "Urdu" if choice == "urdu" else "English"
                return await _generate_and_reply(
                    phone, s["complaint"], s["language"], letter_lang, want_pdf=True
                )
            # not a menu answer: maybe it's a brand-new complaint?
            if _looks_like_complaint(text):
                return await _new_complaint(phone, text)
            return _menu_fallback(s["language"])

        # --- Stage: awaiting clarification (asked ONCE) -----------------------
        if s["stage"] == "awaiting_clarification":
            # Fold whatever they said into the complaint and PROCEED regardless.
            combined = (s["complaint"] + " " + text).strip()
            return await _run_pipeline(phone, combined)

        # --- Default: treat as a (new) complaint ------------------------------
        return await _new_complaint(phone, text)

    except Exception as exc:  # never crash the webhook
        logger.exception("whatsapp handler error: %s", exc)
        return ("معذرت، کچھ مسئلہ ہو گیا۔ براہ کرم دوبارہ کوشش کریں۔\n"
                "Sorry, something went wrong. Please try again.")


async def _new_complaint(phone: str, text: str) -> str:
    lang = detect_language(text)
    _save(phone, language=lang, complaint=text)
    # Acknowledge + run. (The ack is returned together with guidance below; on a
    # real webhook you may send ack first, then the guidance as a second message.)
    return await _run_pipeline(phone, text)


async def _run_pipeline(phone: str, complaint: str) -> str:
    s = _session(phone)
    lang = s["language"]
    resp = await analyze_complaint(complaint, language=lang, letter_language="Urdu")

    # NeedsMoreInfo -> ask ONCE (only when the pipeline judged it ambiguous)
    if getattr(resp, "questions", None) and s["stage"] != "awaiting_clarification":
        _save(phone, stage="awaiting_clarification", complaint=complaint)
        q = resp.questions[0] if resp.questions else ""
        if lang == "Urdu":
            return f"بہتر مدد کے لیے بس اتنا بتائیں:\n{q}"
        return f"To help you better, just tell me:\n{q}"

    # Otherwise we have a full analysis -> guidance + offer PDF
    _save(phone, stage="awaiting_pdf_choice", complaint=complaint)
    guidance = _format_guidance(resp, lang)
    return guidance + "\n\n" + _pdf_menu(lang)


async def _generate_and_reply(phone, complaint, guidance_lang, letter_lang, want_pdf):
    """Re-run with the chosen letter language and return the fill-in note.
    The webhook layer attaches the actual PDF link/file."""
    s = _session(phone)
    resp = await analyze_complaint(complaint, language=guidance_lang, letter_language=letter_lang)
    _save(phone, stage="done")
    fields = getattr(resp, "fields_to_fill", None) or (
        ["نام", "شناختی کارڈ نمبر", "تاریخ", "دستخط"] if guidance_lang == "Urdu"
        else ["Name", "CNIC", "Date", "Signature"]
    )
    # The webhook turns resp.complaint_letter into a PDF; here we return the note.
    return _fill_note(guidance_lang, fields), resp  # tuple: (note, full response)
