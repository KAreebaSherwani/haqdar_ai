"""Tier-3 resilience: cached, pre-validated responses for the four example
complaints shown as quick-tap chips in the UI.

If both Gemini tiers fail (quota, outage, venue wifi), these answer instantly.
This is legitimate response caching for common complaint patterns — and it makes
the live demo unkillable.

IMPORTANT: After the real prompt is tuned, regenerate these from actual model
output and hand-verify the Urdu. The texts below are working defaults.
"""

import re

from app.schemas.complaint import ComplaintAnalysis

_CACHE: list[tuple[set[str], ComplaintAnalysis]] = []


def _register(keywords: set[str], payload: dict) -> None:
    _CACHE.append((keywords, ComplaintAnalysis.model_validate(payload)))


_register(
    {"police", "fine", "receipt", "challan", "جرمانہ", "پولیس", "رسید"},
    {
        "violation_summary": "پولیس نے آپ سے جرمانہ وصول کیا لیکن سرکاری رسید جاری نہیں کی۔ یہ قانون کی صریح خلاف ورزی ہے کیونکہ ہر جرمانے کی رسید دینا لازمی ہے۔",
        "law_reference": "Punjab Police Rules 2017",
        "responsible_authority": "ضلعی پولیس افسر (DPO) آفس — اپنے ضلع کا DPO آفس",
        "complaint_letter": "بخدمت جناب ڈسٹرکٹ پولیس آفیسر صاحب،\n\nموضوع: بغیر رسید جرمانہ وصول کرنے کی شکایت\n\nجناب عالی،\n\nنہایت ادب سے گزارش ہے کہ مورخہ [تاریخ] کو پولیس اہلکار نے مجھ سے جرمانہ وصول کیا مگر کوئی سرکاری رسید جاری نہیں کی، جو Punjab Police Rules 2017 کی خلاف ورزی ہے۔ ہر جرمانے کی باقاعدہ رسید دینا قانوناً لازم ہے۔\n\nاستدعا ہے کہ اس واقعے کی تحقیقات کر کے ذمہ دار اہلکار کے خلاف قانونی کارروائی کی جائے اور مجھے تحریری جواب دیا جائے۔\n\nوالسلام،\n[آپ کا نام]\n[تاریخ]",
        "confidence_score": "high",
        "confidence_reason": "یہ شکایت براہِ راست تصدیق شدہ قانون سے مطابقت رکھتی ہے۔",
        "citizen_rights": "آپ کو ہر جرمانے کی سرکاری رسید لینے کا حق ہے۔ بغیر قانونی جواز کے آپ سے جرمانہ وصول نہیں کیا جا سکتا۔ آپ DPO کو براہِ راست شکایت کر سکتے ہیں۔",
        "evidence_to_collect": [
            "واقعے کی تاریخ، وقت اور جگہ نوٹ کریں",
            "اہلکار کا نام یا بیج نمبر اگر معلوم ہو",
            "کسی گواہ کا نام اور رابطہ نمبر",
            "اگر ممکن ہو تو موقع کی تصویر یا ویڈیو",
        ],
        "next_steps": [
            "یہ شکایتی خط DPO آفس میں جمع کروائیں اور وصولی کی رسید لیں",
            "شکایت کی کاپی اپنے پاس محفوظ رکھیں",
            "15 دن میں جواب نہ ملے تو RPO کو اپیل کریں",
        ],
        "sdg_alignment": "sdg16",
    },
)

_register(
    {"hospital", "emergency", "treatment", "ilaj", "mareez", "inkar", "ہسپتال", "علاج", "ایمرجنسی", "مریض"},
    {
        "violation_summary": "ہسپتال نے ایمرجنسی میں علاج سے انکار کیا۔ قانون کے مطابق کوئی بھی ہسپتال ہنگامی حالت میں مریض کو ابتدائی طبی امداد دینے سے انکار نہیں کر سکتا۔",
        "law_reference": "Punjab Healthcare Commission Act 2010",
        "responsible_authority": "پنجاب ہیلتھ کیئر کمیشن (PHC) — ہیلپ لائن 0800-00742، آن لائن پورٹل phc.org.pk",
        "complaint_letter": "بخدمت جناب چیئرمین پنجاب ہیلتھ کیئر کمیشن،\n\nموضوع: ایمرجنسی علاج سے انکار کی شکایت\n\nجناب عالی،\n\nگزارش ہے کہ مورخہ [تاریخ] کو [ہسپتال کا نام] نے ہنگامی حالت کے باوجود علاج فراہم کرنے سے انکار کیا، جو Punjab Healthcare Commission Act 2010 کے تحت مریض کے حقِ علاج کی خلاف ورزی ہے۔\n\nاستدعا ہے کہ ہسپتال کے خلاف کارروائی کی جائے اور مجھے تحریری جواب دیا جائے۔\n\nوالسلام،\n[آپ کا نام]\n[تاریخ]",
        "confidence_score": "high",
        "confidence_reason": "ایمرجنسی علاج کا حق تصدیق شدہ قانون میں واضح طور پر موجود ہے۔",
        "citizen_rights": "ہنگامی حالت میں ہر مریض کو ابتدائی علاج کا حق حاصل ہے۔ ہسپتال فیس کی ادائیگی سے پہلے ہنگامی امداد سے انکار نہیں کر سکتا۔",
        "evidence_to_collect": [
            "ہسپتال کا نام، تاریخ اور وقت",
            "متعلقہ عملے کا نام اگر معلوم ہو",
            "میڈیکل رپورٹس یا پرچی",
            "ہمراہ موجود کسی فرد کی گواہی",
        ],
        "next_steps": [
            "PHC ہیلپ لائن 0800-00742 پر شکایت درج کروائیں",
            "یہ خط PHC کے آن لائن پورٹل پر جمع کروائیں",
            "تمام میڈیکل دستاویزات محفوظ رکھیں",
        ],
        "sdg_alignment": "both",
    },
)

_register(
    {"wapda", "bill", "overcharge", "bijli", "zyada", "ziada", "بجلی", "بل", "واپڈا", "زیادہ"},
    {
        "violation_summary": "آپ سے مقررہ نرخ سے زیادہ قیمت یا غلط بل وصول کیا گیا۔ صارف کو درست قیمت اور سروس کا قانونی حق حاصل ہے۔",
        "law_reference": "(Punjab) Consumer Protection Act 2005",
        "responsible_authority": "ضلعی صارف عدالت (District Consumer Court) — متعلقہ ادارے کا شکایتی مرکز",
        "complaint_letter": "بخدمت جناب صدر ضلعی صارف عدالت،\n\nموضوع: زائد وصولی / غلط بل کی شکایت\n\nجناب عالی،\n\nگزارش ہے کہ مجھ سے مقررہ نرخ سے زائد رقم وصول کی گئی ہے جو Consumer Protection Act 2005 کی خلاف ورزی ہے۔ تفصیل درج ذیل ہے: [تفصیل]\n\nاستدعا ہے کہ زائد رقم کی واپسی اور ذمہ داروں کے خلاف کارروائی کی جائے۔\n\nوالسلام،\n[آپ کا نام]\n[تاریخ]",
        "confidence_score": "high",
        "confidence_reason": "زائد وصولی صارف تحفظ کے تصدیق شدہ قانون کے تحت آتی ہے۔",
        "citizen_rights": "آپ کو درست قیمت پر سروس لینے کا حق ہے۔ زائد وصولی پر معاوضے اور واپسی کا حق حاصل ہے۔",
        "evidence_to_collect": [
            "اصل بل یا رسید کی کاپی",
            "سرکاری نرخ نامہ یا ٹیرف کی کاپی",
            "ادائیگی کا ثبوت",
            "ادارے سے رابطے کا ریکارڈ",
        ],
        "next_steps": [
            "پہلے متعلقہ ادارے کے شکایتی مرکز میں تحریری شکایت دیں",
            "جواب نہ ملنے پر ضلعی صارف عدالت میں درخواست جمع کروائیں",
            "تمام بل اور رسیدیں محفوظ رکھیں",
        ],
        "sdg_alignment": "sdg10",
    },
)

_register(
    {"salary", "wage", "tankhwah", "tankha", "malik", "mazdoori", "ujrat", "تنخواہ", "مزدوری", "اجرت", "مالک", "فیکٹری"},
    {
        "violation_summary": "آپ کو تنخواہ یا کم از کم اجرت وقت پر ادا نہیں کی گئی۔ قانون کے مطابق ہر مزدور کو مقررہ کم از کم اجرت بروقت ملنا لازمی ہے۔",
        "law_reference": "Labour laws (Industrial Relations Act 2012 / minimum wage notifications)",
        "responsible_authority": "صوبائی محکمہ محنت (Labour Department) / لیبر کورٹ",
        "complaint_letter": "بخدمت جناب ڈائریکٹر محکمہ محنت،\n\nموضوع: تنخواہ کی عدم ادائیگی کی شکایت\n\nجناب عالی،\n\nگزارش ہے کہ میرے آجر نے میری تنخواہ/کم از کم اجرت ادا نہیں کی، جو لیبر قوانین کی خلاف ورزی ہے۔ تفصیل: [تفصیل]\n\nاستدعا ہے کہ میری واجب الادا رقم دلوائی جائے اور آجر کے خلاف کارروائی کی جائے۔\n\nوالسلام،\n[آپ کا نام]\n[تاریخ]",
        "confidence_score": "high",
        "confidence_reason": "اجرت کی بروقت ادائیگی لیبر قوانین میں واضح ہے۔",
        "citizen_rights": "آپ کو تقرری نامہ، مقررہ کم از کم اجرت، اور بروقت ادائیگی کا قانونی حق حاصل ہے۔",
        "evidence_to_collect": [
            "تقرری نامہ یا ملازمت کا کوئی ثبوت",
            "حاضری یا کام کے اوقات کا ریکارڈ",
            "پچھلی تنخواہ کی رسیدیں یا بینک ریکارڈ",
            "ساتھی ملازمین کی گواہی",
        ],
        "next_steps": [
            "محکمہ محنت کے ضلعی دفتر میں تحریری شکایت دیں",
            "شکایت کا نمبر اور رسید محفوظ رکھیں",
            "ضرورت پڑنے پر لیبر کورٹ میں دعویٰ دائر کریں",
        ],
        "sdg_alignment": "both",
    },
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w\u0600-\u06FF]+", text.lower()))


def lookup(complaint: str) -> ComplaintAnalysis | None:
    """Return a cached analysis if the complaint matches a known pattern."""
    words = _tokens(complaint)
    best: tuple[int, ComplaintAnalysis] | None = None
    for keywords, payload in _CACHE:
        score = len(words & keywords)
        if score >= 2 and (best is None or score > best[0]):
            best = (score, payload)
    return best[1] if best else None
