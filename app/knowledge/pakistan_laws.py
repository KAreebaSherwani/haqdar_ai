"""Verified Pakistani law knowledge base — structured for retrieval.

Single source of truth. Each provision is a discrete, embeddable chunk with its
own metadata. The same data powers:
  - the vector store (each provision embedded for semantic retrieval)
  - the inclusion fallback (all provisions joined into one grounding block)
  - the citation verifier (the registry of valid law names)

HARD RULE: verify every provision against the official source before shipping.
An unverified law is worse than a missing one — it breaks the whole guarantee.
"""

LAW_PROVISIONS: list[dict] = [
    {
        "id": "police-receipt",
        "domain": "police",
        "law": "Punjab Police Rules 2017",
        "provision": "Police must issue an official receipt for any fine collected, and may not collect a fine without lawful written authority.",
        "authority": "District Police Officer (DPO) of the citizen's district; escalation to Regional Police Officer (RPO).",
        "authority_contact": "DPO Office (district HQ). Punjab Police complaint helpline: 8787.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "police-detention",
        "domain": "police",
        "law": "Punjab Police Rules 2017",
        "provision": "A citizen may not be detained or fined without stated legal grounds and proper documentation.",
        "authority": "District Police Officer (DPO); Provincial Police Complaint Authority.",
        "authority_contact": "DPO Office (district HQ). Punjab Police helpline: 8787.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "consumer-overcharge",
        "domain": "consumer",
        "law": "Punjab Consumer Protection Act 2005",
        "provision": "Traders may not charge above the displayed or notified price; consumers are entitled to refund or compensation for defective goods or services.",
        "authority": "District Consumer Court / Consumer Protection Council.",
        "authority_contact": "District Consumer Court (district courts complex). Punjab portal: dpc.punjab.gov.pk.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "rti-access",
        "domain": "rti",
        "law": "Right of Access to Information Act 2017",
        "provision": "Every citizen has the right to information held by federal public bodies, normally within 10 working days of a written request; refusal must be in writing with reasons.",
        "authority": "Pakistan Information Commission (PIC), Islamabad. For Punjab bodies: Punjab Information Commission under the Punjab Transparency and RTI Act 2013.",
        "authority_contact": "Pakistan Information Commission: rti.gov.pk. Punjab Information Commission: pic.punjab.gov.pk.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "rti-access-punjab",
        "domain": "rti",
        "law": "Punjab Transparency and Right to Information Act 2013",
        "provision": "Every citizen has the right to information held by Punjab public bodies; the designated officer must respond, normally within 14 working days, and any refusal must be in writing with reasons and is appealable to the Punjab Information Commission.",
        "authority": "Punjab Information Commission.",
        "authority_contact": "Punjab Information Commission: pic.punjab.gov.pk.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "labour-wages",
        "domain": "labour",
        "law": "Labour laws (Industrial Relations Act 2012; minimum wage notifications)",
        "provision": "Workers are entitled to a written appointment letter and timely payment of at least the notified minimum wage, without unlawful deductions.",
        "authority": "Provincial Labour Department / Labour Court.",
        "authority_contact": "Punjab Labour Department: labour.punjab.gov.pk. District Labour Office.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "health-emergency",
        "domain": "healthcare",
        "law": "Punjab Healthcare Commission Act 2010",
        "provision": "Patients have the right to emergency medical treatment; healthcare establishments must not refuse stabilising emergency care and must meet required standards.",
        "authority": "Punjab Healthcare Commission (PHC).",
        "authority_contact": "PHC helpline: 0800-00742. Complaint portal: phc.org.pk.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "traffic-challan",
        "domain": "traffic",
        "law": "Motor Vehicle Ordinance 1965",
        "provision": "A traffic challan must state the specific violation and an official receipt is mandatory for any fine; a citizen may contest a challan before the designated traffic magistrate.",
        "authority": "Chief Traffic Officer (CTO) / SSP Traffic of the district.",
        "authority_contact": "District Traffic Police office. Punjab Traffic helpline: 1124 (where available).",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "municipal-services",
        "domain": "municipal",
        "law": "Punjab Local Government Act",
        "provision": "Local governments are responsible for basic municipal services (sanitation, water supply, streetlights, encroachment) and must address citizen complaints about service failures.",
        "authority": "Municipal Committee / Local Government complaint cell.",
        "authority_contact": "District Municipal Committee office. Punjab LG portal: lgcd.punjab.gov.pk.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "utility-billing",
        "domain": "utility",
        "law": "Consumer service rules (NEPRA / OGRA complaint mechanisms)",
        "provision": "Utility consumers (electricity, gas) may dispute incorrect or excessive billing and are entitled to a corrected bill through the regulator's complaint mechanism.",
        "authority": "Relevant utility company complaint cell; escalation to NEPRA (electricity) or OGRA (gas), or WASA for water.",
        "authority_contact": "NEPRA: nepra.org.pk. OGRA: ogra.org.pk. Local utility billing office.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "education-fees",
        "domain": "education",
        "law": "Private educational institutions fee-regulation rules",
        "provision": "Private schools must follow fee-regulation rules and may not levy unapproved or excessive fee increases; parents may complain to the regulatory authority.",
        "authority": "District Education Authority / Private Schools Regulatory Authority (PSRA).",
        "authority_contact": "Punjab PSRA: psra.punjab.gov.pk. District Education Authority office.",
        "last_reviewed": "2026-06-10",
    },
    {
        "id": "women-harassment",
        "domain": "women",
        "law": "Protection against Harassment of Women at the Workplace Act 2010",
        "provision": "Women have the right to a harassment-free workplace; every organisation must have an inquiry committee, and complaints may be escalated to the Ombudsperson.",
        "authority": "Workplace inquiry committee; Federal/Provincial Ombudsperson for Harassment.",
        "authority_contact": "Punjab Women Helpline: 1043. Federal helpline: 1099.",
        "last_reviewed": "2026-06-10",
    },
]


def all_law_names() -> set[str]:
    return {p["law"] for p in LAW_PROVISIONS}


def build_context(provisions: list[dict]) -> str:
    lines = ["VERIFIED PAKISTANI LAW REFERENCE — cite ONLY from these entries:\n"]
    for p in provisions:
        lines.append(
            f"- Law: {p['law']}\n"
            f"  Provision: {p['provision']}\n"
            f"  Responsible authority: {p['authority']}\n"
            f"  Contact: {p['authority_contact']}\n"
        )
    lines.append(
        "\nGUIDANCE: clear match -> confidence 'high'. Partial match or missing facts -> "
        "'medium'. Outside these provisions (criminal violence, property/family disputes) -> "
        "'needs_verification' and recommend a lawyer or district free legal aid committee. "
        "NEVER invent a law name or section number."
    )
    return "\n".join(lines)


LAWS_CONTEXT = build_context(LAW_PROVISIONS)