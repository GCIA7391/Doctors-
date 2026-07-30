#!/usr/bin/env python3
"""
Deterministic derivation of the requested enrichment columns from evidence that
is already on disk. No web access, no inference beyond the rules stated here.

Why this exists: result files under state/results/ are the raw research record.
Rather than rewriting them (which would destroy the audit trail), the new
columns are *derived* at merge time by a pure function, so the mapping is
reproducible and reviewable. Values an agent supplied explicitly always win;
derivation only fills gaps.

Run directly for a derivation report:
    python3 scripts/derive_fields.py
"""
import json, os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import (CONF_HIGH, CONF_MEDIUM, CONF_LOW, CONF_UNKNOWN,
                    VALID_CONFIDENCE, STATUS_AMBIGUOUS, STATUS_BASELINE,
                    VERIFY_PAGE, VERIFY_SEARCH, VERIFY_NONE)

HOSPITAL_TABLE_PATH = "state/hospital_contacts.json"

# Domains that count as an *official* source for the confidence rubric: the
# hospitals' own sites, Apollo's own booking platform, government registries,
# and the scholarly identity registries.
OFFICIAL_DOMAIN_PATTERNS = [
    r"apollohospitals\.com", r"apollo247\.com", r"aighospitals\.com",
    r"aigindia\.net", r"yashodahospitals\.com", r"carehospitals\.com",
    r"rainbowhospitals\.in", r"gleneagleshospitals\.co\.in",
    r"citineurocentre\.com", r"cityneurocenter\.com", r"starhospitals\.in",
    r"\.gov\.in", r"\.gov$", r"\.nic\.in", r"\.edu$", r"\.edu\.in",
    r"\.ac\.in", r"\.ac\.uk", r"orcid\.org", r"scholar\.google\.",
    r"nmc\.org\.in", r"tsmc\.",
]
# Reputable directories: corroborate identity, but do not by themselves make a
# match "official" for confidence-band purposes.
DIRECTORY_DOMAIN_PATTERNS = [
    r"practo\.com", r"lybrate\.com", r"skedoc\.com", r"hexahealth\.com",
    r"justdial\.com", r"myupchar\.com", r"sehat\.com", r"credihealth\.com",
    r"vaidam\.com", r"clinicspots\.com", r"bajajfinservhealth\.in",
    r"researchgate\.net", r"doximity\.com", r"healthgrades\.com",
]

URLRE = re.compile(r"https?://[^\s,;)\]]+", re.I)


def _load_table(path=HOSPITAL_TABLE_PATH):
    with open(path) as f:
        return json.load(f)


def _domain(url):
    m = re.match(r"https?://([^/]+)", url.strip(), re.I)
    return m.group(1).lower() if m else ""


def _is_official(url):
    d = _domain(url)
    return any(re.search(p, d) for p in OFFICIAL_DOMAIN_PATTERNS)


def _is_directory(url):
    d = _domain(url)
    return any(re.search(p, d) for p in DIRECTORY_DOMAIN_PATTERNS)


def all_urls(res):
    """Every URL referenced anywhere in a result, deduplicated."""
    blob = "\n".join(str(res.get(k, "") or "") for k in res)
    return list(dict.fromkeys(URLRE.findall(blob)))


def official_source_count(res):
    """Distinct official-domain sources backing this identity."""
    return len({_domain(u) for u in all_urls(res) if _is_official(u)})


def directory_source_count(res):
    return len({_domain(u) for u in all_urls(res) if _is_directory(u)})


# --------------------------------------------------------------------------- #
# confidence band
# --------------------------------------------------------------------------- #
def confidence_band(res):
    """Map evidence to the requested High/Medium/Low/Unknown vocabulary.

    High    verified by 2+ independent official sources
    Medium  strong evidence but only one official source
    Low     partial match only
    Unknown unable to confidently verify (incl. ambiguous identity)
    """
    if res.get("status") == STATUS_AMBIGUOUS:
        return CONF_UNKNOWN
    # an agent that supplied a band explicitly is authoritative
    band = str(res.get("confidence_band", "") or "").strip()
    if band in VALID_CONFIDENCE:
        return band

    off = official_source_count(res)
    dirs = directory_source_count(res)
    raw = res.get("confidence")
    numeric = raw if isinstance(raw, (int, float)) else None

    if numeric is None:
        if off >= 2:
            return CONF_HIGH
        if off == 1:
            return CONF_MEDIUM
        return CONF_LOW if dirs else CONF_UNKNOWN

    if numeric >= 90 and off >= 2:
        return CONF_HIGH
    if numeric >= 80 and (off >= 1 or dirs >= 1):
        return CONF_MEDIUM
    if numeric >= 90 and off == 1:
        return CONF_MEDIUM
    if numeric > 0:
        return CONF_LOW
    return CONF_UNKNOWN


# --------------------------------------------------------------------------- #
# tier 1 / tier 2 field derivation
# --------------------------------------------------------------------------- #
def _first(*vals):
    for v in vals:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def professional_phone(res):
    """A phone that reaches the doctor's own practice.

    A hospital switchboard is deliberately NOT a professional phone - it is an
    indirect route and is reported as such.
    """
    return _first(res.get("professional_phone"),
                  res.get("clinic_number"),
                  res.get("appointment_number"))


def appointment_link(res):
    """A booking page for this specific doctor.

    Only pages that are unambiguously per-doctor booking pages qualify:
    an agent-supplied link, an Apollo247 doctor page, or a Practo doctor page.
    A hospital group's general appointment page is an *indirect* route and is
    reported there instead, so this column never overstates what it is.
    """
    explicit = str(res.get("appointment_link", "") or "").strip()
    if explicit:
        return explicit
    for key in ("directory_profile", "practo"):
        u = str(res.get(key, "") or "").strip()
        if not u:
            continue
        d = _domain(u)
        if "apollo247.com" in d and "/doctors/" in u:
            return u
        if "practo.com" in d and "/doctor/" in u:
            return u
    return ""


def clinic_url(res):
    """The doctor's own clinic/practice site, when publicly evidenced."""
    explicit = str(res.get("clinic_url", "") or "").strip()
    if explicit:
        return explicit
    site = str(res.get("personal_website", "") or "").strip()
    if site and res.get("owns_clinic"):
        return site
    return ""


# --------------------------------------------------------------------------- #
# indirect contact - every row gets one
# --------------------------------------------------------------------------- #
def _branch_entry(hosp_entry, address):
    a = str(address or "").lower()
    best = None
    for name, info in (hosp_entry.get("branches") or {}).items():
        if name in a:
            # prefer the most specific (longest) branch name that matches
            if best is None or len(name) > len(best[0]):
                best = (name, info)
    return best


def indirect_contact(rec, res, table):
    """Return (method, details) - the best legal non-direct route to the doctor.

    Doctor-specific institutional contacts found during research come first;
    the verified hospital-group route is always appended so this is never empty.
    """
    methods, details = [], []

    if res:
        sec = str(res.get("secretary_number", "") or "").strip()
        if sec:
            methods.append("Secretary")
            details.append(f"Secretary: {sec}")
        dept_email = str(res.get("department_email", "") or "").strip()
        if dept_email:
            methods.append("Department email")
            details.append(f"Department email: {dept_email}")
        hosp_email = str(res.get("hospital_email", "") or "").strip()
        if hosp_email:
            methods.append("Hospital email")
            details.append(f"Hospital email: {hosp_email}")
        hosp_num = str(res.get("hospital_number", "") or "").strip()
        if hosp_num:
            methods.append("Hospital switchboard")
            details.append(f"Hospital switchboard: {hosp_num}")
        explicit_m = str(res.get("indirect_method", "") or "").strip()
        explicit_d = str(res.get("indirect_details", "") or "").strip()
        if explicit_m:
            methods.append(explicit_m)
        if explicit_d:
            details.append(explicit_d)

    entry = table.get(rec.get("hospital", ""))
    if entry:
        appt = entry.get("appointment_page", "")
        contact = entry.get("contact_page", "")
        branch = _branch_entry(entry, rec.get("address", ""))
        methods.append("Hospital appointment / contact page")
        line = f"{entry['group']} appointment page: {appt}"
        if contact and contact != appt:
            line += f" | contact page: {contact}"
        details.append(line)

        if branch and str(branch[1].get("phone", "") or "").strip():
            methods.append("Hospital branch reception")
            details.append(
                f"{entry['group']} - {branch[0].title()} branch: "
                f"{branch[1]['phone']} (published; see {branch[1].get('page') or contact})")
        elif str(entry.get("helpline", "") or "").strip():
            methods.append("Hospital appointment helpline")
            details.append(
                f"{entry.get('helpline_label') or 'Hospital helpline'}: "
                f"{entry['helpline']} (published; see {contact})")

        if str(entry.get("email", "") or "").strip():
            methods.append("Hospital enquiry email")
            details.append(f"{entry['group']} enquiries: {entry['email']} (see {contact})")

    # dedupe, preserving order
    methods = list(dict.fromkeys(m for m in methods if m))
    details = list(dict.fromkeys(d for d in details if d))
    return "; ".join(methods), "\n".join(details)


# --------------------------------------------------------------------------- #
# best way to reach - the tier ladder from the brief
# --------------------------------------------------------------------------- #
def best_way(derived, res, indirect_method, indirect_details=""):
    explicit = str((res or {}).get("best_way", "") or "").strip()
    if explicit:
        return explicit
    if derived.get("professional_email"):
        return f"Direct professional email: {derived['professional_email']}"
    if derived.get("professional_phone"):
        return f"Published practice phone: {derived['professional_phone']}"
    if derived.get("appointment_link"):
        return f"Book via the doctor's own appointment page: {derived['appointment_link']}"
    if derived.get("hospital_profile"):
        return (f"Official hospital profile (carries the hospital's booking route): "
                f"{derived['hospital_profile']}")
    if derived.get("clinic_url"):
        return f"Clinic website: {derived['clinic_url']}"
    if derived.get("personal_website"):
        return f"Professional website: {derived['personal_website']}"
    if derived.get("linkedin"):
        return f"Professional LinkedIn: {derived['linkedin']}"
    if indirect_method:
        # name the route AND carry the actionable detail, so the cell is usable
        # on its own without cross-referencing another column
        primary = (indirect_details or "").split("\n")[0].strip()
        first_method = indirect_method.split(";")[0].strip()
        if primary:
            return f"Indirect Contact - {first_method}: {primary}"
        return f"Indirect Contact - {first_method}"
    return ""


# --------------------------------------------------------------------------- #
# top-level
# --------------------------------------------------------------------------- #
def derive(rec, res, table):
    """Return the derived field dict for one doctor.

    rec  = master_ranked.json record (source data, always present)
    res  = state/results/row_<id>.json content, or None if not yet researched
    """
    d = {}
    r = res or {}

    # identity / classification -------------------------------------------
    d["specialization"] = _first(r.get("specialization"), rec.get("department"))
    d["country"] = _first(r.get("country"), "India")

    # pass-through of researched fields ------------------------------------
    for k in ("professional_email", "hospital_profile", "linkedin",
              "google_scholar", "researchgate", "orcid", "twitter",
              "facebook", "instagram", "youtube", "personal_website",
              "practo", "directory_profile", "lybrate", "other_profiles",
              "verified_role", "verified_experience", "hni_signals",
              "sources", "notes"):
        d[k] = str(r.get(k, "") or "").strip()
    d["owns_clinic"] = bool(r.get("owns_clinic"))

    # tier 1 / tier 2 derivation -------------------------------------------
    d["professional_phone"] = professional_phone(r)
    d["appointment_link"] = appointment_link(r)
    d["clinic_url"] = clinic_url(r)

    # indirect route (always populated) ------------------------------------
    d["indirect_method"], d["indirect_details"] = indirect_contact(rec, res, table)

    # best way to reach ----------------------------------------------------
    d["best_way"] = best_way(d, res, d["indirect_method"], d["indirect_details"])

    # audit ----------------------------------------------------------------
    if res:
        d["confidence_band"] = confidence_band(r)
        d["status"] = r.get("status", "")
        d["verification_method"] = _first(r.get("verification_method"), VERIFY_PAGE)
        d["enriched_on"] = str(r.get("enriched_on", "") or "")
    else:
        d["confidence_band"] = CONF_UNKNOWN
        d["status"] = STATUS_BASELINE
        d["verification_method"] = VERIFY_NONE
        d["enriched_on"] = ""
        d["notes"] = ("Baseline row: source data plus the verified hospital-level "
                      "contact route. No doctor-specific research performed yet.")
        d["sources"] = ""

    d["official_source_count"] = official_source_count(r) if res else 0
    d["experience_discrepancy"] = experience_discrepancy(rec, res)
    d["affiliation_flag"] = affiliation_flag(res)
    return d


def experience_discrepancy(rec, res):
    """Flag where the published experience contradicts the source list.

    The source list's experience column drives the priority ranking, so a
    disagreement matters: it means the queue may be ordered on a wrong figure.
    Reported, never silently corrected - the source row stays as given.
    """
    if not res:
        return ""
    src = rec.get("experience_years")
    ver = str(res.get("verified_experience", "") or "")
    if src is None or not ver:
        return ""
    m = re.search(r"(\d+)", ver)
    if not m:
        return ""
    pub = int(m.group(1))
    if abs(pub - src) > 3:
        return (f"Source list says {src} yrs; published profile says {pub} yrs "
                f"(difference {abs(pub - src)})")
    return ""


# Phrases research notes use when the doctor's hospital may not be the one the
# source list names: a move, a dual appointment, or an unconfirmed affiliation.
AFFILIATION_DOUBT_RE = re.compile(
    r"stale|no longer|has moved|moved ~|former employer|current employer"
    r"|affiliation[^.]{0,40}(not confirmed|unconfirmed|conflict|contradic)"
    r"|(not confirmed|unconfirmed|conflict|contradic)[^.]{0,40}affiliation"
    r"|second attachment|dual affiliation|overlapping affiliation", re.I)


def affiliation_flag(res):
    """Flag rows where the source list's hospital may be wrong or incomplete.

    This is a KEYWORD SCAN OF THE RESEARCH NOTES, not a derived fact - unlike
    the experience check there is no numeric field to compare, so the honest
    thing is to surface what the note says and label how it was found. Always
    read the Notes column before acting on it.
    """
    if not res:
        return ""
    notes = str(res.get("notes", "") or "")
    if AFFILIATION_DOUBT_RE.search(notes):
        return ("Research notes question the hospital in the source list "
                "(possible move, dual appointment, or unconfirmed unit) - "
                "read Notes before contacting")
    return ""


def has_direct_contact(d):
    return bool(d.get("professional_email") or d.get("professional_phone")
                or d.get("appointment_link"))


def has_any_online_presence(d):
    return bool(d.get("hospital_profile") or d.get("clinic_url")
                or d.get("linkedin") or d.get("personal_website")
                or d.get("google_scholar") or d.get("researchgate")
                or d.get("orcid") or d.get("practo")
                or d.get("directory_profile"))


def main():
    table = _load_table()
    recs = json.load(open("state/master_ranked.json"))
    n_res = 0
    bands = {}
    stats = {"email": 0, "phone": 0, "appt": 0, "linkedin": 0,
             "direct": 0, "indirect_only": 0, "no_indirect": 0}
    for rec in recs:
        p = f"state/results/row_{rec['row_id']}.json"
        res = json.load(open(p)) if os.path.exists(p) else None
        if res:
            n_res += 1
        d = derive(rec, res, table)
        bands[d["confidence_band"]] = bands.get(d["confidence_band"], 0) + 1
        if res:
            stats["email"] += bool(d["professional_email"])
            stats["phone"] += bool(d["professional_phone"])
            stats["appt"] += bool(d["appointment_link"])
            stats["linkedin"] += bool(d["linkedin"])
            if has_direct_contact(d):
                stats["direct"] += 1
            else:
                stats["indirect_only"] += 1
        if not d["indirect_method"]:
            stats["no_indirect"] += 1

    print(f"doctors: {len(recs)}   researched: {n_res}   baseline: {len(recs)-n_res}")
    print("confidence bands (all rows):", bands)
    print("researched rows ->", stats)
    print(f"rows with NO indirect route: {stats['no_indirect']}  (must be 0)")


if __name__ == "__main__":
    main()
