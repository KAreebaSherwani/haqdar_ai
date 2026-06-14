"""Schemas for the /analyze endpoint.

One Pydantic model serves three roles:
1. Validates the API request.
2. Is passed to Gemini as response_schema (structured output constraint).
3. Defines the API response contract.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceScore(str, Enum):
    high = "high"
    medium = "medium"
    needs_verification = "needs_verification"


class SdgAlignment(str, Enum):
    sdg16 = "sdg16"
    sdg10 = "sdg10"
    both = "both"


class ComplaintRequest(BaseModel):
    complaint: str = Field(min_length=3, max_length=2000)
    district: str | None = Field(default=None, max_length=50, description="Optional, personalizes the letter + anonymous civic map")
    name: str | None = Field(default=None, max_length=80, description="Optional, fills the letter signature (never stored)")
    incident_date: str | None = Field(default=None, max_length=30, description="Optional incident date for the letter (never stored)")
    language: str = Field(default="Urdu", max_length=20, description="Guidance language (Urdu, English, Punjabi, Sindhi, Pashto). The formal letter always stays Urdu.")
    letter_language: str = Field(default="Urdu", max_length=10, description="Formal complaint letter language: 'Urdu' or 'English' (the document languages Pakistani authorities accept).")


class ComplaintAnalysis(BaseModel):
    """The structured legal analysis Gemini is constrained to produce."""

    violation_summary: str = Field(description="Plain Urdu, 2-3 sentences: what happened and why it is wrong")
    law_reference: str = Field(description="Exact law name from the verified reference only")
    responsible_authority: str = Field(description="Exact office name and contact to complain to")
    complaint_letter: str = Field(
        description=(
            "Full formal complaint letter in legal Urdu. Structure: addressee line "
            "(e.g. بخدمت جناب ...), subject line (موضوع:), body describing the violation, "
            "clear demand for action, date, and complainant placeholder [آپ کا نام]."
        )
    )
    confidence_score: ConfidenceScore
    confidence_reason: str = Field(description="One sentence in Urdu explaining the confidence level")
    citizen_rights: str = Field(description="2-3 rights the citizen has, in plain Urdu")
    evidence_to_collect: list[str] = Field(description="3-4 pieces of evidence to gather, in Urdu")
    next_steps: list[str] = Field(description="Exactly 3 action steps in Urdu")
    sdg_alignment: SdgAlignment


class ResponseMeta(BaseModel):
    request_id: str
    model_used: str
    processing_ms: int
    cached: bool = False
    citation_verified: bool = True
    retrieval_source: str = "inclusion"
    top_score: float = 1.0
    db_version: str = "June 2026"
    last_legal_review: str = "2026-06-10"


class RelevantLaw(BaseModel):
    law: str
    authority: str
    contact: str = ""
    provision: str = ""


class NeedsMoreInfoResponse(BaseModel):
    """Returned when the complaint is too thin to answer safely."""

    status: str = "needs_more_info"
    questions: list[str]
    detected_domain: str = "general"
    meta: ResponseMeta


class AnalyzeResponse(ComplaintAnalysis):
    status: str = "ok"
    reference_id: str = ""
    primary_domain: str = "general"
    secondary_domain: str | None = None
    relevant_laws: list[RelevantLaw] = []
    confidence_value: float = 0.0  # numeric companion to confidence_score
    meta: ResponseMeta
