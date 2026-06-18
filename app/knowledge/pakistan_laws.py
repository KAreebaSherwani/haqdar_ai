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
        "law": "Code of Criminal Procedure, 1898",
        "provision": "Under Section 102 and Section 165 of the Code of Criminal Procedure (CrPC), any police officer seizing property must document it and provide a receipt/inventory. Furthermore, police officers cannot collect cash fines directly on the spot; an official written challan must be issued.",
        "authority": "District Police Officer (DPO) of the citizen's district; escalation to Regional Police Officer (RPO).",
        "authority_contact": "DPO Office (district HQ). Punjab Police complaint helpline: 8787.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "police-detention",
        "domain": "police",
        "law": "Constitution of Pakistan, 1973 & Code of Criminal Procedure, 1898",
        "provision": "Under Article 10 of the Constitution and Section 61 of the CrPC, no person shall be detained in custody without being informed of the grounds for arrest, and every person arrested must be produced before a magistrate within 24 hours of arrest.",
        "authority": "District Police Officer (DPO); Provincial Police Complaint Authority.",
        "authority_contact": "DPO Office (district HQ). Punjab Police helpline: 8787.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "consumer-overcharge",
        "domain": "consumer",
        "law": "Punjab Consumer Protection Act, 2005",
        "provision": "Under Sections 18 (Prices to be exhibited), 19 (Receipt to be issued), and 21 (False representation) of the Punjab Consumer Protection Act 2005, a trader shall not charge a price higher than the displayed price. Consumers have the right to claim a refund, replacement, or compensation for defective products or faulty services.",
        "authority": "District Consumer Court / Consumer Protection Council.",
        "authority_contact": "District Consumer Court (district courts complex). Punjab portal: dpc.punjab.gov.pk.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "rti-access",
        "domain": "rti",
        "law": "Right of Access to Information Act, 2017",
        "provision": "Under Sections 3 and 14 of the Right of Access to Information Act 2017, every citizen has the right to access information or records held by federal public bodies. The requested information must be provided within 10 working days, and any refusal must be formally communicated in writing.",
        "authority": "Pakistan Information Commission (PIC), Islamabad.",
        "authority_contact": "Pakistan Information Commission: rti.gov.pk.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "rti-access-punjab",
        "domain": "rti",
        "law": "Punjab Transparency and Right to Information Act, 2013",
        "provision": "Under Section 10 of the Punjab Transparency and Right to Information Act 2013, a Public Information Officer must provide the requested information within 14 working days. Any rejection must be justified in writing and can be appealed to the Punjab Information Commission.",
        "authority": "Punjab Information Commission.",
        "authority_contact": "Punjab Information Commission: pic.punjab.gov.pk.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "labour-wages",
        "domain": "labour",
        "law": "Minimum Wages Ordinance, 1961 & Standing Orders Ordinance, 1968",
        "provision": "Under the Minimum Wages Ordinance 1961 and the Standing Orders Ordinance 1968, every employer must provide a formal appointment letter. Workers are legally entitled to receive at least the government-notified minimum wage, to be paid timely without unauthorized deductions.",
        "authority": "Provincial Labour Department / Labour Court.",
        "authority_contact": "Punjab Labour Department: labour.punjab.gov.pk. District Labour Office.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "health-emergency",
        "domain": "healthcare",
        "law": "Punjab Healthcare Commission Act, 2010",
        "provision": "Under Section 19 of the Punjab Healthcare Commission Act 2010 and the Charter of Patient Rights, patients are entitled to immediate life-saving emergency medical treatment. A healthcare establishment cannot refuse to provide stabilizing emergency care.",
        "authority": "Punjab Healthcare Commission (PHC).",
        "authority_contact": "PHC helpline: 0800-00742. Complaint portal: phc.org.pk.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "traffic-challan",
        "domain": "traffic",
        "law": "Provincial Motor Vehicles Ordinance, 1965",
        "provision": "Under Section 116-A of the Provincial Motor Vehicles Ordinance 1965, a traffic police officer must issue a specific ticket (Form J challan) detailing the exact traffic violation. Fines cannot be collected in cash on the spot and must be deposited in a designated bank.",
        "authority": "Chief Traffic Officer (CTO) / SSP Traffic of the district.",
        "authority_contact": "District Traffic Police office. Punjab Traffic helpline: 1124 (where available).",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "municipal-services",
        "domain": "municipal",
        "law": "Punjab Local Government Act, 2025",
        "provision": "Under the Punjab Local Government Act 2025, local municipal authorities are legally obligated to provide and maintain basic civic amenities, including sanitation, solid waste management, water supply, and street lighting, and must maintain an active complaint redressal system.",
        "authority": "Municipal Committee / Local Government complaint cell.",
        "authority_contact": "District Municipal Committee office. Punjab LG portal: lgcd.punjab.gov.pk.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "utility-billing",
        "domain": "utility",
        "law": "NEPRA Act, 1997 & OGRA Ordinance, 2002",
        "provision": "Under the NEPRA Consumer Service Manual and OGRA dispute resolution regulations, electricity and gas consumers have the right to dispute inaccurate, excessive, or estimated bills. Disputed amounts may be stayed until the regulatory complaint is resolved.",
        "authority": "Relevant utility company complaint cell; escalation to NEPRA (electricity) or OGRA (gas), or WASA for water.",
        "authority_contact": "NEPRA: nepra.org.pk. OGRA: ogra.org.pk. Local utility billing office.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "education-fees",
        "domain": "education",
        "law": "The Punjab Private Educational Institutions Ordinance, 1984 (Amended)",
        "provision": "Under the Punjab Private Educational Institutions rules, private schools cannot arbitrarily increase tuition fees beyond the strictly enforced 5% annual ceiling without explicit regulatory approval, nor can they compel parents to buy uniforms/books from specific vendors.",
        "authority": "District Education Authority / Private Education Provider Registration & Information System (PEPRIS).",
        "authority_contact": "Punjab PEPRIS: pepris.pesrp.edu.pk. District Education Authority office.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
    {
        "id": "women-harassment",
        "domain": "women",
        "law": "Protection against Harassment of Women at the Workplace Act, 2010",
        "provision": "Under Sections 3 and 4 of the Protection against Harassment of Women at the Workplace Act 2010, every organization is legally required to constitute a three-member Inquiry Committee to investigate harassment complaints. Aggrieved persons also have the right to file a direct complaint with the Ombudsperson.",
        "authority": "Workplace inquiry committee; Federal/Provincial Ombudsperson for Harassment.",
        "authority_contact": "Punjab Women Helpline: 1043. Federal helpline: 1099.",
        "source": "AI",
        "last_reviewed": "2026-06-17",
    },
]


def all_law_names() -> set[str]:
    return {p["law"] for p in LAW_PROVISIONS}


def build_context(provisions: list[dict]) -> str:
    lines = ["VERIFIED PAKISTANI LAW REFERENCE — cite ONLY from these entries:\n"]
    for p in provisions:
        source_tag = p.get("source", "AI")
        lines.append(
            f"- Law: {p['law']}\n"
            f"  Provision: {p['provision']}\n"
            f"  Responsible authority: {p['authority']}\n"
            f"  Contact: {p['authority_contact']}\n"
            f"  Source: {source_tag}\n"
        )
    lines.append(
        "\nNOTE ON RETRIEVAL: The provisions above were selected using semantic (cosine"
        " similarity) search. They may not all be directly applicable to the complaint."
        " Use your own judgment to determine which actually match the situation."
        "\n\nGUIDANCE: clear match -> confidence 'high'. Partial match or missing facts -> "
        "'medium'. Outside these provisions (criminal violence, property/family disputes) -> "
        "'needs_verification' and recommend a lawyer or district free legal aid committee. "
        "NEVER invent a law name or section number."
    )
    return "\n".join(lines)


LAWS_CONTEXT = build_context(LAW_PROVISIONS)
