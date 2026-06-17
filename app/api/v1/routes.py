"""API v1 routers: /analyze, /rights, /stats, /health."""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core import vector_store
from app.schemas.complaint import AnalyzeResponse, ComplaintRequest, NeedsMoreInfoResponse
from app.schemas.rights import RightsRequest, RightsResponse
from app.services.analysis_service import analyze_complaint
from app.services.pdf_service import build_letter_pdf
from app.services.rights_service import explain_rights

router = APIRouter()

_INJECTION_PATTERNS = ("ignore previous", "ignore all previous", "system prompt", "you are now")


def _guard(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Input cannot be empty")
    lowered = cleaned.lower()
    if any(p in lowered for p in _INJECTION_PATTERNS):
        raise HTTPException(status_code=400, detail="Invalid input")
    return cleaned


@router.post("/analyze", response_model=AnalyzeResponse | NeedsMoreInfoResponse, tags=["core"])
async def analyze(req: ComplaintRequest) -> AnalyzeResponse | NeedsMoreInfoResponse:
    """Citizen complaint -> full legal action package."""
    complaint = _guard(req.complaint)
    try:
        return await analyze_complaint(complaint, req.district, req.name, req.incident_date, req.language, req.letter_language)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="سروس عارضی طور پر دستیاب نہیں۔ براہ کرم دوبارہ کوشش کریں۔",
        ) from None


@router.post("/rights", response_model=RightsResponse, tags=["core"])
async def rights(req: RightsRequest) -> RightsResponse:
    """Scenario -> rights education answer."""
    scenario = _guard(req.scenario)
    try:
        return await explain_rights(scenario, req.language)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="سروس عارضی طور پر دستیاب نہیں۔ براہ کرم دوبارہ کوشش کریں۔",
        ) from None


class LetterPdfRequest(BaseModel):
    reference_id: str = "HQD-2026-0001"
    complaint_letter: str
    law_reference: str = ""
    responsible_authority: str = ""


@router.post("/letter/pdf", tags=["core"])
def letter_pdf(req: LetterPdfRequest) -> Response:
    """Render the complaint letter as a downloadable Urdu PDF."""
    if not req.complaint_letter.strip():
        raise HTTPException(status_code=400, detail="No letter content")
    s = get_settings()
    from datetime import date

    pdf_bytes = build_letter_pdf(
        reference_id=req.reference_id,
        complaint_letter=req.complaint_letter,
        law_reference=req.law_reference,
        authority=req.responsible_authority,
        db_version=s.db_version,
        generated_date=date.today().isoformat(),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{req.reference_id}.pdf"'},
    )


@router.get("/stats", tags=["dashboard"])
def stats() -> dict:
    """REAL civic aggregates — every number is a complaint this system processed.

    Anonymous by design: only domain, district, and date are ever stored.
    """
    from app.services import report_store

    return report_store.stats()


@router.get("/report/{reference_id}", tags=["dashboard"])
def report_lookup(reference_id: str) -> dict:
    """Look up an anonymous report by its reference number (no personal data)."""
    from app.services import report_store

    found = report_store.get_by_reference(reference_id)
    if not found:
        raise HTTPException(status_code=404, detail="Reference not found")
    return found


@router.post("/whatsapp", tags=["whatsapp"])
async def whatsapp_webhook(request: Request) -> Response:
    """Twilio WhatsApp webhook. Runs the bot, and when the user picks a PDF,
    generates it, saves it to the public /files dir, and delivers it as media."""
    import os
    from datetime import date
    from xml.sax.saxutils import escape

    from app.services import whatsapp_bot

    form = await request.form()
    body = (form.get("Body") or "").strip()
    sender = form.get("From") or form.get("WaId") or "unknown"

    # Voice note processing
    try:
        num_media = int(form.get("NumMedia") or "0")
    except (TypeError, ValueError):
        num_media = 0
        
    if num_media > 0 and not body:
        media_url = form.get("MediaUrl0")
        media_type = form.get("MediaContentType0") or "audio/ogg"
        if media_url and media_type.startswith("audio"):
            try:
                import httpx
                from app.core.ai_client import transcribe_audio

                s = get_settings()
                auth = (getattr(s, "twilio_account_sid", "") or "",
                        getattr(s, "twilio_auth_token", "") or "")
                async with httpx.AsyncClient(timeout=30) as hc:
                    r = await hc.get(media_url, auth=auth if auth[0] else None)
                    r.raise_for_status()
                    audio_bytes = r.content
                body = await transcribe_audio(audio_bytes, mime_type=media_type)
            except Exception:
                from xml.sax.saxutils import escape as _esc
                msg = ("معذرت، آواز سمجھ نہیں آئی۔ براہ کرم اپنا مسئلہ ٹائپ کریں۔\n"
                       "Sorry, I couldn't understand the voice note. Please type your problem.")
                twiml = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message><Body>{_esc(msg)}</Body></Message></Response>"
                return Response(content=twiml, media_type="text/xml; charset=utf-8")

    # Await the pipeline handler cleanly
    reply = await whatsapp_bot.handle_message(sender, body)

    # Cleanly unpack if the awaited execution returns our data tuple
    media_url_out = None
    if isinstance(reply, tuple):
        note, full = reply
        reply_text = note
        try:
            s = get_settings()
            pdf_bytes = build_letter_pdf(
                reference_id=full.reference_id,
                complaint_letter=full.complaint_letter,
                law_reference=full.law_reference,
                authority=full.responsible_authority,
                db_version=s.db_version,
                generated_date=date.today().isoformat(),
            )
            os.makedirs("/tmp/haqdar_pdfs", exist_ok=True)
            fname = f"{full.reference_id}.pdf"
            with open(f"/tmp/haqdar_pdfs/{fname}", "wb") as f:
                f.write(pdf_bytes)
            media_url_out = f"{s.public_base_url.rstrip('/')}/files/{fname}"
        except Exception:
            reply_text = note + "\n\n(درخواست بنانے میں مسئلہ ہوا — دوبارہ کوشش کریں / "
            reply_text += "Could not generate the PDF — please try again.)"
    else:
        reply_text = reply

    # Format the explicit TwiML XML payload response instructions back to Twilio
    msg = f"<Message><Body>{escape(str(reply_text))}</Body>"
    if media_url_out:
        msg += f"<Media>{escape(str(media_url_out))}</Media>"
    msg += "</Message>"
    
    twiml = f"<?xml version='1.0' encoding='UTF-8'?><Response>{msg}</Response>"
    return Response(content=twiml, media_type="text/xml; charset=utf-8")


@router.post("/transcribe", tags=["core"])
async def transcribe(audio: UploadFile = File(...)) -> dict:
    """Transcribe an uploaded voice recording (Urdu/English) to text via Gemini."""
    try:
        data = await audio.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty audio")
        from app.core.ai_client import transcribe_audio
        mime = audio.content_type or "audio/ogg"
        text = await transcribe_audio(data, mime_type=mime)
        return {"text": text}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="آواز کو متن میں تبدیل نہیں کیا جا سکا۔ براہ کرم ٹائپ کریں۔ "
                   "(Could not transcribe audio — please type instead.)",
        ) from None


@router.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness check — also the keep-alive ping target."""
    s = get_settings()
    return {
        "status": "online",
        "service": s.app_name,
        "primary_model": s.primary_model,
        "fallback_model": s.fallback_model,
        "vector_store_ready": vector_store.is_ready(),
        "db_version": s.db_version,
    }