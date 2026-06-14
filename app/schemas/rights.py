"""Schemas for the /rights (Know Your Rights) endpoint."""

from pydantic import BaseModel, Field

from app.schemas.complaint import ResponseMeta


class RightsRequest(BaseModel):
    scenario: str = Field(min_length=3, max_length=2000)
    language: str = Field(default="Urdu", max_length=20, description="Guidance language (Urdu, English, Punjabi, Sindhi, Pashto).")


class RightsAnswer(BaseModel):
    """Structured rights-education answer Gemini is constrained to produce."""

    your_right: str = Field(description="The citizen's right in this situation, in plain Urdu")
    law_that_protects: str = Field(description="Exact law name from the verified reference only")
    evidence_to_collect: list[str] = Field(description="3-4 pieces of proof to gather, in Urdu")
    next_steps: list[str] = Field(description="Exactly 3 action steps in Urdu")
    responsible_authority: str = Field(description="Which office handles this, with contact if known")


class RightsResponse(RightsAnswer):
    meta: ResponseMeta