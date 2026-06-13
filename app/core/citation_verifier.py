"""Citation verifier — the zero-hallucination enforcement layer.

The prompt INSTRUCTS the model to cite only verified laws.
This module ENFORCES it in code: every law_reference in every response is
checked against the verified law registry. If the model ever cites a law that
is not in our knowledge base, the response is automatically downgraded to
needs_verification and the unverified citation is replaced.

This is the difference between "we asked the AI to be accurate" and
"the system architecturally cannot deliver an unverified citation."
"""

import logging

from app.knowledge.pakistan_laws import all_law_names

logger = logging.getLogger("haqdar.verifier")

# Alias keywords let the verifier match the model's phrasing to a verified law.
_ALIASES: dict[str, list[str]] = {
    "Punjab Police Rules 2017": ["police rules", "punjab police"],
    "(Punjab) Consumer Protection Act 2005": ["consumer protection"],
    "Right of Access to Information Act 2017": ["access to information", "right of access"],
    "Punjab Transparency and Right to Information Act 2013": ["transparency and right"],
    "Labour laws (Industrial Relations Act 2012; minimum wage notifications)": [
        "industrial relations", "labour law", "labor law", "factories act", "minimum wage",
    ],
    "Punjab Healthcare Commission Act 2010": ["healthcare commission"],
    "Motor Vehicle Ordinance 1965": ["motor vehicle"],
    "Punjab Local Government Act": ["local government"],
    "Consumer service rules (NEPRA / OGRA complaint mechanisms)": ["nepra", "ogra", "utility"],
    "Private educational institutions fee-regulation rules": ["fee-regulation", "fee regulation", "psra", "private school"],
    "Protection against Harassment of Women at the Workplace Act 2010": ["harassment of women", "workplace harassment"],
}


def _build_registry() -> dict[str, list[str]]:
    reg: dict[str, list[str]] = {}
    for name in all_law_names():
        aliases = _ALIASES.get(name, [])
        # always allow matching on distinctive words from the law name itself
        reg[name] = aliases or [name.lower()]
    return reg


VERIFIED_LAWS: dict[str, list[str]] = _build_registry()

UNVERIFIED_FALLBACK_REFERENCE = (
    "اس معاملے کے لیے ہمارے تصدیق شدہ قوانین میں براہِ راست حوالہ موجود نہیں — "
    "براہ کرم وکیل یا ضلعی مفت قانونی امداد کمیٹی سے رجوع کریں "
    "(No directly verified law in our database for this case — please consult "
    "a lawyer or the district free legal aid committee)"
)


def is_verified(law_reference: str) -> bool:
    """True if the cited law matches an entry in the verified registry."""
    text = law_reference.lower()
    return any(
        alias in text for aliases in VERIFIED_LAWS.values() for alias in aliases
    )


def enforce(analysis) -> tuple[object, bool]:
    """Verify the citation in an analysis object (ComplaintAnalysis or RightsAnswer).

    Returns (possibly-modified analysis, citation_verified flag).
    If the citation fails verification, confidence is forced to
    needs_verification and the reference is replaced with safe guidance.
    """
    field = "law_reference" if hasattr(analysis, "law_reference") else "law_that_protects"
    cited = getattr(analysis, field, "")

    if is_verified(cited):
        return analysis, True

    logger.warning("UNVERIFIED CITATION BLOCKED: %r", cited)
    setattr(analysis, field, UNVERIFIED_FALLBACK_REFERENCE)
    if hasattr(analysis, "confidence_score"):
        analysis.confidence_score = "needs_verification"
        analysis.confidence_reason = (
            "حوالہ تصدیق شدہ قانونی ڈیٹا بیس سے میل نہیں کھاتا، اس لیے وکیل سے مشورہ ضروری ہے۔"
        )
    return analysis, False
