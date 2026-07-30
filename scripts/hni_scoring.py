#!/usr/bin/env python3
"""
Evidence-based HNI prospect scoring.

WHAT THIS IS AND IS NOT
-----------------------
Every flag below is set ONLY when the row's own researched evidence text says so
- the verified role, the publicly stated HNI signals, the specialty, or the
research notes. Nothing is inferred from a name, a hospital, or a hunch.

"Estimated HNI Probability", "Estimated Wealth Tier" and "Prospect Score" are
NOT financial assessments and NOT claims about anyone's assets. They are a
transparent count of PUBLIC PROFESSIONAL SIGNALS - practice ownership,
leadership title, international training, high-fee specialty, stated procedure
volumes - weighted by a documented rubric. Two doctors with the same score have
the same public signals, nothing more.

"Estimated Private Patient Volume" is populated ONLY when a source publicly
states a volume (e.g. "20,000 cardiac surgeries"). It is never estimated.

Run directly for a distribution report:
    python3 scripts/hni_scoring.py
"""
import json, os, re, sys, glob

# --------------------------------------------------------------------------- #
# signal detection - each pattern must MATCH THE ROW'S OWN EVIDENCE TEXT
# --------------------------------------------------------------------------- #
def _ev(rec, res):
    """The evidence blob a flag may be drawn from. Researched text only."""
    r = res or {}
    parts = [
        str(r.get("verified_role", "") or ""),
        str(r.get("hni_signals", "") or ""),
        str(r.get("verified_experience", "") or ""),
        str(r.get("specialization", "") or ""),
        str(r.get("notes", "") or ""),
        str(rec.get("department", "") or ""),
    ]
    return "\n".join(parts)


def _has(blob, *patterns):
    return any(re.search(p, blob, re.I) for p in patterns)


# --- leadership / seniority -------------------------------------------------
P_DIRECTOR = (r"\bdirector\b", r"\bclinical director\b", r"\bmedical director\b")
P_CHAIRMAN = (r"\bchairman\b", r"\bchairperson\b", r"\bchair\b(?!.*\bside\b)")
P_HOD = (r"\bhead of (the )?department\b", r"\bHOD\b", r"\bdepartment head\b",
         r"\bgroup head\b", r"\bhead[, ]+(department|dept)\b")
P_SENIOR = (r"\bsenior consultant\b", r"\bsr\.? consultant\b", r"\bchief\b")
P_PROF = (r"\bprofessor\b", r"\bprof\.\b", r"\bassoc\.? prof\b",
          r"\bassociate professor\b", r"\bfaculty\b")
P_FOUNDER = (r"\bfounder\b", r"\bco-founder\b", r"\bfounded\b", r"\bestablished (his|her|their) own\b")

# --- ownership / entrepreneurship ------------------------------------------
# Deliberately narrow: must name a clinic or practice, not merely "his own
# website". The agent-set `owns_clinic` boolean is the primary signal; these
# patterns only catch cases where the evidence text is explicit.
P_OWN_CLINIC = (r"\bown(s|ed)? (a |his |her |their )?(clinic|practice|centre|center)\b",
                r"\b(his|her|their) own (clinic|practice|centre|center)\b",
                r"\bfounder of .{0,40}(clinic|practice|centre|center|hospital)\b",
                r"\beponymous (clinic|practice)\b",
                r"\bruns? (a |his |her |their )?(own )?(clinic|practice|chain)\b",
                r"\bclinic chain\b", r"\bfounded and leads\b")
P_OWN_HOSPITAL = (r"\bowns? (a |his |her |their )?hospital\b",
                  r"\bfounder .{0,40}hospital\b", r"\bhospital .{0,20}he founded\b",
                  r"\bwhich he founded\b", r"\bwhich she founded\b",
                  r"\bfounded and leads\b")
P_MULTI_SITE = (r"\bmultiple hospitals\b", r"\bmultiple simultaneous\b",
                r"\bdual affiliation\b", r"\balso consults?\b", r"\balso practises\b",
                r"\balso practices\b", r"\btwo hospital affiliations\b",
                r"\bacross multiple\b", r"\bclinic chain\b", r"\bmultiple clinics\b",
                r"\bdual/overlapping\b", r"\bconcurrent\b",
                r"\b(two|three|four|multiple|several) (practice )?locations?\b",
                r"\bpractice locations\b", r"\bdual[- ]campus\b",
                r"\bsecond (practice|site|clinic)\b", r"\bboth .{0,25}(campuses|branches)\b")
P_ENTREPRENEUR = (r"\bfounder\b", r"\bco-founder\b", r"\bentrepreneur\b",
                  r"\bclinic chain\b", r"\bstartup\b", r"\bdirector of .{0,30}(pvt|private limited)\b")

# --- training / standing ----------------------------------------------------
_COUNTRIES = (r"usa|u\.s\.|united states|uk|united kingdom|england|scotland|"
              r"germany|france|italy|japan|australia|singapore|canada|israel|"
              r"korea|netherlands|greece|switzerland|sweden|belgium|spain|"
              r"austria|taiwan|hong kong|dubai|ireland|new zealand")
P_INTL = (rf"\bfellowship[^.]{{0,60}}({_COUNTRIES})\b",
          rf"\b({_COUNTRIES})\b[^.]{{0,40}}\bfellowship\b",
          rf"\btrain(ed|ing)[^.]{{0,40}}({_COUNTRIES})\b",
          rf"\bobservership[^.]{{0,40}}({_COUNTRIES})\b",
          # Foreign college fellowships / board certifications
          r"\bFRCS\b", r"\bMRCP\b", r"\bMRCOG\b", r"\bFACC\b", r"\bFACS\b",
          r"\bFRCP\b", r"\bFRCR\b", r"\bFRCA\b", r"\bFEBU\b", r"\bFEBS\b",
          r"\bFICS\b", r"\bFSBRT\b", r"\bFCBT\b", r"\bFAMS\b", r"\bSCAI\b",
          r"\bABIM\b", r"\bAmerican Board\b", r"\bboard[- ]certified\b",
          r"\bEuropean Board\b", r"\bRoyal College\b",
          # Named foreign institutions that recur in this dataset
          r"\bHarvard\b", r"\bTufts\b", r"\bMayo\b", r"\bCleveland Clinic\b",
          r"\bJohns Hopkins\b", r"\bAOSpine\b", r"\bOsaka\b", r"\bFreeman Hospital\b",
          r"\bNewcastle\b", r"\bLoyola\b", r"\bOregon Health\b", r"\bMie\b",
          r"\bTata Memorial\b(?!.*\bIndia only\b)")
P_SPEAKER = (r"\bconference\b", r"\bspeaker\b", r"\bfaculty at\b", r"\bproctor\b",
             r"\bpresented .{0,30}(paper|poster)\b", r"\bkeynote\b",
             r"\bEditor\b", r"\bEditorial\b", r"\bpast president\b",
             r"\bpresident\b", r"\bexecutive committee\b")
P_SOCIETY = (r"\bsociety\b", r"\bassociation\b", r"\bcollege of\b", r"\bacademy\b",
             r"\bFOGSI\b", r"\bIMA\b", r"\bCSI\b", r"\bmember of\b")
P_AWARD = (r"\baward\b", r"\brecognition\b", r"\bLimca\b", r"\bIndia Today\b",
           r"\bbest paper\b", r"\bhonou?r\b")
P_MEDIA = (r"\bmedia\b", r"\binterview\b", r"\bnational press\b", r"\bspokesperson\b",
           r"\bexplainer\b", r"\btelevision\b", r"\bpress\b")

# --- high-fee / luxury practice --------------------------------------------
LUXURY_SPECIALTIES = {
    "Cosmetic": (r"\bcosmetic\b", r"\baesthetic\b", r"\bplastic surgery\b", r"\bplastic &\b", r"\bhair transplant\b"),
    "IVF": (r"\bIVF\b", r"\bfertility\b", r"\binfertility\b", r"\breproductive medicine\b", r"\bART\b"),
    "Oncology": (r"\boncolog", r"\bcancer\b", r"\bhemato-?onco", r"\bHIPEC\b"),
    "Cardiac": (r"\bcardiac\b", r"\bcardiolog", r"\bcardiothoracic\b", r"\bCTVS\b", r"\bTAVI\b", r"\bTAVR\b", r"\belectrophysiolog"),
    "Neuro": (r"\bneuro", r"\bspine surgery\b", r"\bskull base\b"),
    "Robotic": (r"\brobotic\b", r"\bda vinci\b"),
    "Transplant": (r"\btransplant\b",),
    "Orthopaedic": (r"\borthopa?edic\b", r"\bjoint replacement\b", r"\barthroscopy\b"),
    "Bariatric": (r"\bbariatric\b", r"\bmetabolic surgery\b"),
}

# --- negative signals -------------------------------------------------------
P_JUNIOR = (r"\bjunior resident\b", r"\bregistrar\b", r"\btrainee\b",
            r"\bassistant professor only\b", r"\bearly career\b",
            r"\bjunior consultant\b(?!.*consultant track)")

PREMIUM_GROUPS = {"Apollo Hospitals", "AIG Hospital", "Yashoda Hospitals",
                  "Care Hospitals", "Gleneagles Aware Hospital", "Star Hospital",
                  "Citi Neuro Centre", "Rainbow Children's Hospital"}

# A publicly stated volume: a number, then up to a few words of procedure
# description, then a volume noun. Deliberately tolerant of the descriptor
# ("750 SRS/SRT procedures", "20,000 successful cardiac surgeries") because the
# alternative is silently dropping real, quoted evidence.
VOLUME_RE = re.compile(
    # Not a 4-digit year: graduation years and council registration numbers were
    # being picked up as volumes. No ')' or '.' allowed in the descriptor either,
    # so a match cannot run across a sentence or parenthesis boundary.
    r"\b(?!(?:19|20)\d{2}\b)([\d][\d,]{2,})\s*\+?\s*(?:[A-Za-z/&-]+\s+){0,4}"
    r"(?:surgeries|surgery|procedures|operations|implants|transplants|cases|"
    r"deliveries|angioplasties|replacements|consultations)\b",
    re.I)


def _years(rec, res):
    """Best-evidenced years of experience, preferring researched over source."""
    ver = str((res or {}).get("verified_experience", "") or "")
    m = re.search(r"(\d+)\s*\+?\s*(?:years|yrs)", ver, re.I)
    if m:
        return int(m.group(1))
    if rec.get("experience_years") is not None:
        return rec["experience_years"]
    return None


def score(rec, res):
    """Return the HNI signal dict for one doctor. Empty-ish when unresearched."""
    out = {k: "" for k in HNI_COLUMNS_KEYS}
    if not res:
        out["prospect_score"] = ""
        out["outreach_priority"] = ""
        out["hni_probability"] = "Unknown"
        out["wealth_tier"] = "Unknown"
        return out

    blob = _ev(rec, res)
    pts = 0
    leadership = []

    # --- leadership -------------------------------------------------------
    if _has(blob, *P_CHAIRMAN):
        out["chairman"] = "Yes"; leadership.append("Chairman"); pts += 12
    if _has(blob, *P_DIRECTOR):
        out["director"] = "Yes"; leadership.append("Director"); pts += 10
    if _has(blob, *P_HOD):
        out["hod"] = "Yes"; leadership.append("Head of Department"); pts += 8
    if _has(blob, *P_SENIOR):
        out["senior_consultant"] = "Yes"; leadership.append("Senior Consultant"); pts += 5
    if _has(blob, *P_PROF):
        out["professor"] = "Yes"; leadership.append("Professor/Faculty"); pts += 5
    out["leadership_roles"] = "; ".join(leadership)

    # --- ownership / entrepreneurship -------------------------------------
    owns_clinic = bool(res.get("owns_clinic")) or _has(blob, *P_OWN_CLINIC)
    if owns_clinic:
        out["own_clinic"] = "Yes"; out["practice_ownership"] = "Yes"; pts += 14
    if _has(blob, *P_OWN_HOSPITAL):
        out["own_hospital"] = "Yes"; out["practice_ownership"] = "Yes"; pts += 8
    if _has(blob, *P_MULTI_SITE):
        out["multi_location"] = "Yes"; pts += 7
    if _has(blob, *P_ENTREPRENEUR):
        out["entrepreneur"] = "Yes"; pts += 6
    if res.get("clinic_url") or res.get("personal_website"):
        out["private_practice"] = "Yes"; pts += 4

    # --- training / standing ----------------------------------------------
    if _has(blob, *P_INTL):
        out["international_training"] = "Yes"; pts += 9
    if _has(blob, *P_SPEAKER):
        out["conference_speaker"] = "Yes"; pts += 5
    if _has(blob, *P_AWARD) or _has(blob, *P_MEDIA):
        out["known_brand"] = "Yes"; pts += 4
    elif _has(blob, *P_SOCIETY):
        pts += 2

    # --- high-fee specialty -----------------------------------------------
    lux = [name for name, pats in LUXURY_SPECIALTIES.items() if _has(blob, *pats)]
    if lux:
        out["luxury_specialty"] = "; ".join(sorted(lux))
        # cap the specialty contribution so a long specialty string cannot
        # outweigh hard ownership/leadership evidence
        pts += min(12, 4 * len(lux))
        out["luxury_indicators"] = out["luxury_specialty"]

    # --- premium group ----------------------------------------------------
    if rec.get("hospital") in PREMIUM_GROUPS:
        out["premium_group"] = "Yes"; pts += 3

    # --- experience -------------------------------------------------------
    yrs = _years(rec, res)
    if yrs is not None:
        out["years_experience"] = yrs
        if yrs >= 30: pts += 10
        elif yrs >= 20: pts += 7
        elif yrs >= 12: pts += 4
        elif yrs < 7: pts -= 5

    # --- publicly stated volumes (never estimated) ------------------------
    vol = VOLUME_RE.search(blob)
    if vol:
        out["private_patient_volume"] = vol.group(0).strip()
        pts += 5

    # --- negative signals -------------------------------------------------
    if _has(blob, *P_JUNIOR):
        pts -= 10

    # --- confidence damping: don't score unverified identity highly -------
    band = res.get("confidence_band") or ""
    if band == "Low":
        pts = int(pts * 0.6)
    elif band == "Unknown" or res.get("status") == "Ambiguous Match":
        pts = int(pts * 0.4)

    pts = max(0, min(100, pts))
    out["prospect_score"] = pts

    # --- derived bands ----------------------------------------------------
    if pts >= 60:
        out["hni_probability"] = "High"; out["wealth_tier"] = "Tier 1 signals"
        out["outreach_priority"] = "P1 - contact first"
        out["family_office_fit"] = "Yes"; out["pms_fit"] = "Yes"
    elif pts >= 40:
        out["hni_probability"] = "Medium"; out["wealth_tier"] = "Tier 2 signals"
        out["outreach_priority"] = "P2"
        out["pms_fit"] = "Yes"
    elif pts >= 22:
        out["hni_probability"] = "Low"; out["wealth_tier"] = "Tier 3 signals"
        out["outreach_priority"] = "P3"
    else:
        out["hni_probability"] = "Unknown"; out["wealth_tier"] = "Unknown"
        out["outreach_priority"] = "P4 - insufficient public signal"
    return out


HNI_COLUMNS_KEYS = [
    "hni_probability", "wealth_tier", "practice_ownership", "multi_location",
    "own_hospital", "own_clinic", "director", "chairman", "hod",
    "senior_consultant", "professor", "international_training",
    "luxury_indicators", "luxury_specialty", "years_experience",
    "leadership_roles", "conference_speaker", "private_practice",
    "entrepreneur", "private_patient_volume", "premium_group", "known_brand",
    "family_office_fit", "pms_fit", "prospect_score", "outreach_priority",
]


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import collections
    recs = json.load(open("state/master_ranked.json"))
    dist = collections.Counter()
    prio = collections.Counter()
    flags = collections.Counter()
    scored = 0
    for rec in recs:
        p = f"state/results/row_{rec['row_id']}.json"
        res = json.load(open(p)) if os.path.exists(p) else None
        s = score(rec, res)
        if res:
            scored += 1
            dist[s["hni_probability"]] += 1
            prio[s["outreach_priority"]] += 1
            for k in ("own_clinic", "own_hospital", "director", "chairman", "hod",
                      "international_training", "entrepreneur", "multi_location",
                      "known_brand", "private_patient_volume"):
                if s[k]:
                    flags[k] += 1
    print(f"scored {scored} researched doctors")
    print("HNI probability:", dict(dist))
    print("outreach priority:", dict(prio))
    print("signal counts:", dict(flags))


if __name__ == "__main__":
    main()
