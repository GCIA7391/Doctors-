#!/usr/bin/env python3
"""
Build Doctors_Enriched.xlsx - the deliverable.

Sheets
  1 "Enriched Doctors"           every doctor, all enrichment columns. Rows not
                                 yet researched still carry source data plus the
                                 verified hospital-level contact route, so no row
                                 is ever a dead end.
  2 "Direct Contacts"            only doctors with a Tier-1 direct route.
  3 "Duplicates & Manual Review" same-name collisions and ambiguous identities.
  4 "Summary"                    the requested run statistics.
  5 "README"                     methodology, column meanings, caveats.

Usage: python3 scripts/merge_final.py
"""
import json, os, sys, collections
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import (OUTPUT_COLUMNS, REQUESTED_COLUMNS, RESULT_KEY_TO_COLUMN,
                    HNI_COLUMNS, HNI_KEY_TO_COLUMN,
                    CONF_HIGH, CONF_MEDIUM, CONF_LOW, CONF_UNKNOWN,
                    STATUS_AMBIGUOUS, STATUS_REVIEW, VERIFY_PAGE, VERIFY_SEARCH)
from derive_fields import (derive, _load_table, has_direct_contact,
                           has_any_online_presence)
from hni_scoring import score as hni_score

OUT = "Doctors_Enriched.xlsx"

HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
REQ_FILL = PatternFill("solid", fgColor="2E75B6")   # the 26 requested columns
THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

BAND_FILL = {
    CONF_HIGH:    PatternFill("solid", fgColor="C6EFCE"),
    CONF_MEDIUM:  PatternFill("solid", fgColor="FFEB9C"),
    CONF_LOW:     PatternFill("solid", fgColor="FFC7CE"),
    CONF_UNKNOWN: PatternFill("solid", fgColor="EDEDED"),
}

WIDTHS = {
    "Doctor Name": 26, "Specialization": 26, "Hospital": 20, "Department": 24,
    "City": 16, "Country": 10, "Professional Email": 26,
    "Professional Phone": 18, "Appointment Link": 42,
    "Hospital Profile URL": 42, "Clinic URL": 32, "LinkedIn URL": 34,
    "Google Scholar": 30, "ResearchGate": 30, "ORCID": 24,
    "Professional X": 24, "Professional Instagram": 26,
    "Professional Facebook": 26, "Professional YouTube": 26,
    "Professional Website": 32, "Indirect Contact Method": 34,
    "Indirect Contact Details": 60, "Best Way To Reach": 52,
    "Confidence Score": 12, "Sources Used": 54, "Notes": 46,
    "Experience": 12, "Address": 30, "Verification Method": 16,
    "Status": 22, "Enriched On": 14, "Priority Rank": 9,
    "HNI Priority Score": 10, "Verified Role/Title": 30,
    "Verified Experience": 22, "Owns Clinic/Practice": 11, "HNI Signals": 40,
    "Practo Profile": 34, "Apollo247/Directory Profile": 40,
    "Lybrate Profile": 30, "Other Professional Profiles": 34,
    "Review Reason": 44, "Experience Discrepancy": 46,
    "Affiliation Flag": 48,
    "Prospect Score (0-100)": 10, "Outreach Priority": 22,
    "Estimated HNI Probability": 12, "Estimated Wealth Tier": 15,
    "Potential Family Office Fit": 11, "Potential PMS Fit": 11,
    "Practice Ownership": 11, "Own Clinic": 9, "Own Hospital": 9,
    "Multiple Practice Locations": 12, "Private Practice": 10,
    "Entrepreneur": 11, "Leadership Roles": 34, "Director": 9,
    "Chairman": 9, "Head of Department": 11, "Senior Consultant": 11,
    "Professor": 9, "International Training": 12, "Conference Speaker": 11,
    "Known Medical Brand": 11, "Luxury Practice Indicators": 30,
    "High-Fee Specialty Indicators": 30,
    "Estimated Private Patient Volume": 24, "Premium Hospital Group": 11,
    "Years Experience": 10,
}

HYD_LOCALITIES = ["hyderabad", "secunderabad", "jubilee hills", "banjara hills",
                  "gachibowli", "financial district", "kondapur", "madhapur",
                  "hitec city", "hitech city", "kukatpally", "manikonda",
                  "malakpet", "somajiguda", "begumpet", "lb nagar", "l b nagar",
                  "hyderguda", "attapur", "nacharam", "sainikpuri", "alwal",
                  "miyapur", "uppal", "ameerpet", "kompally", "nizampet",
                  "bachupally", "shamshabad", "kokapet", "nallagandla",
                  "tellapur", "chandanagar", "chanda nagar", "habsiguda",
                  "karkhana", "malkajgiri", "himayatnagar", "narayanguda",
                  "kachiguda", "mehdipatnam", "tolichowki", "dilsukhnagar"]


def load_result(row_id):
    p = f"state/results/row_{row_id}.json"
    return json.load(open(p)) if os.path.exists(p) else None


def _city_of(rec):
    a = str(rec.get("address") or "").lower()
    if "secunderabad" in a:
        return "Secunderabad (Hyderabad)"
    if any(l in a for l in HYD_LOCALITIES):
        return "Hyderabad"
    # every hospital group in this source list is Hyderabad-based
    return "Hyderabad"


def build_row(rec, res, table):
    """One output row: source data + derived/researched enrichment."""
    row = {c: "" for c in OUTPUT_COLUMNS}
    d = derive(rec, res, table)

    # original source data, preserved verbatim
    row["Doctor Name"] = rec["name"]
    row["Department"] = rec["department"]
    row["Hospital"] = rec["hospital"]
    row["Experience"] = rec["experience_raw"]
    row["Address"] = rec["address"]
    row["City"] = (res or {}).get("city") or rec.get("city_guess") or _city_of(rec)
    row["Priority Rank"] = rec["priority_rank"]
    row["HNI Priority Score"] = rec["priority_score"]

    # everything derived / researched
    for key, col in RESULT_KEY_TO_COLUMN.items():
        if key in d:
            v = d[key]
            if isinstance(v, bool):
                v = "Yes" if v else ""
            row[col] = v if v is not None else ""

    # HNI prospect qualification, scored from this row's own evidence only
    h = hni_score(rec, res)
    for key, col in HNI_KEY_TO_COLUMN.items():
        v = h.get(key, "")
        row[col] = v if v is not None else ""
    d["_hni"] = h
    return row, d


def style_header(ws, cols, highlight_requested=True):
    for j, col in enumerate(cols, 1):
        c = ws.cell(row=1, column=j, value=col)
        c.fill = (REQ_FILL if (highlight_requested and col in REQUESTED_COLUMNS)
                  else HDR_FILL)
        c.font = HDR_FONT
        c.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=True)
        c.border = BORDER
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 44


def write_grid(ws, cols, rows, band_col="Confidence Score"):
    style_header(ws, cols)
    band_idx = cols.index(band_col) + 1 if band_col in cols else None
    for i, row in enumerate(rows, start=2):
        for j, col in enumerate(cols, 1):
            c = ws.cell(row=i, column=j, value=row.get(col, ""))
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = BORDER
            c.font = Font(size=9)
        if band_idx:
            f = BAND_FILL.get(row.get(band_col))
            if f:
                ws.cell(row=i, column=band_idx).fill = f
    for j, col in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(j)].width = WIDTHS.get(col, 24)


def main():
    table = _load_table()
    recs = json.load(open("state/master_ranked.json"))

    rows, derived = [], []
    for rec in recs:
        res = load_result(rec["row_id"])
        row, d = build_row(rec, res, table)
        row["_researched"] = res is not None      # helper, never a sheet column
        rows.append(row)
        derived.append(d)

    wb = openpyxl.Workbook()

    # ---- Sheet 1: everything ------------------------------------------------
    ws = wb.active
    ws.title = "Enriched Doctors"
    write_grid(ws, OUTPUT_COLUMNS, rows)

    # ---- Sheet 2: direct contacts only -------------------------------------
    dcols = ["Doctor Name", "Specialization", "Hospital", "City",
             "Professional Email", "Professional Phone", "Appointment Link",
             "Hospital Profile URL", "LinkedIn URL", "Best Way To Reach",
             "Confidence Score", "Verification Method", "Priority Rank"]
    direct_rows = [r for r, d in zip(rows, derived)
                   if r["_researched"] and has_direct_contact(d)]
    write_grid(wb.create_sheet("Direct Contacts"), dcols, direct_rows)

    # ---- Sheet 2b: HNI prospect ranking ------------------------------------
    pcols = ["Prospect Score (0-100)", "Outreach Priority",
             "Estimated HNI Probability", "Doctor Name", "Specialization",
             "Hospital", "City", "Leadership Roles", "Practice Ownership",
             "Own Clinic", "Multiple Practice Locations",
             "International Training", "High-Fee Specialty Indicators",
             "Estimated Private Patient Volume", "Years Experience",
             "Best Way To Reach", "Professional Email", "Professional Phone",
             "Appointment Link", "LinkedIn URL", "Confidence Score",
             "Potential Family Office Fit", "Potential PMS Fit"]
    prospect_rows = sorted(
        [r for r in rows if r["_researched"] and r["Prospect Score (0-100)"] != ""],
        key=lambda r: -int(r["Prospect Score (0-100)"]))
    write_grid(wb.create_sheet("HNI Prospect Ranking"), pcols, prospect_rows)

    # ---- Sheet 3: duplicates & manual review -------------------------------
    name_counts = collections.Counter(r["Doctor Name"].strip().lower() for r in rows)
    dup_names = {n for n, c in name_counts.items() if c > 1}
    review_rows = []
    for r in rows:
        reasons = []
        if r["Doctor Name"].strip().lower() in dup_names:
            reasons.append("Duplicate name in source list")
        if r["Status"] == STATUS_AMBIGUOUS:
            reasons.append("Ambiguous identity - contacts withheld")
        if r["Status"] == STATUS_REVIEW:
            reasons.append("Insufficient public info to verify confidently")
        if r["_researched"] and r["Confidence Score"] == CONF_LOW:
            reasons.append("Partial match only (Low confidence)")
        if r["Experience Discrepancy"]:
            reasons.append("Source experience contradicts published profile")
        if r["Affiliation Flag"]:
            reasons.append("Hospital in source list may be stale or incomplete")
        if reasons:
            rr = dict(r)
            rr["Review Reason"] = "; ".join(reasons)
            review_rows.append(rr)
    rcols = ["Doctor Name", "Specialization", "Hospital", "Department", "City",
             "Review Reason", "Confidence Score", "Status",
             "Experience", "Experience Discrepancy", "Affiliation Flag",
             "Hospital Profile URL", "Best Way To Reach", "Notes",
             "Priority Rank"]
    write_grid(wb.create_sheet("Duplicates & Manual Review"), rcols, review_rows)

    # ---- Sheet 4: summary ---------------------------------------------------
    total = len(rows)
    researched = [(r, d) for r, d in zip(rows, derived) if r["_researched"]]
    n_res = len(researched)
    bands = collections.Counter(r["Confidence Score"] for r, _ in researched)
    n_email = sum(1 for r, _ in researched if r["Professional Email"])
    n_phone = sum(1 for r, _ in researched if r["Professional Phone"])
    n_linked = sum(1 for r, _ in researched if r["LinkedIn URL"])
    n_appt = sum(1 for r, _ in researched if r["Appointment Link"])
    n_direct = sum(1 for _, d in researched if has_direct_contact(d))
    n_indirect_only = sum(1 for _, d in researched
                          if not has_direct_contact(d)
                          and not has_any_online_presence(d))
    n_profile_only = sum(1 for _, d in researched
                         if not has_direct_contact(d)
                         and has_any_online_presence(d))
    n_no_contact = sum(1 for r in rows if not r["Indirect Contact Method"]
                       and not r["Best Way To Reach"])
    n_ambiguous = sum(1 for r in rows if r["Status"] == STATUS_AMBIGUOUS)
    n_review = sum(1 for r in rows if r["Status"] == STATUS_REVIEW)
    dup_rows = sum(1 for r in rows if r["Doctor Name"].strip().lower() in dup_names)
    n_exp_disc = sum(1 for r in rows if r["Experience Discrepancy"])
    _pri = collections.Counter(r["Outreach Priority"] for r, _ in researched)
    n_p1 = _pri.get("P1 - contact first", 0)
    n_p2 = _pri.get("P2", 0)
    n_p3 = _pri.get("P3", 0)
    n_p4 = _pri.get("P4 - insufficient public signal", 0)
    n_own = sum(1 for r, _ in researched if r["Practice Ownership"])
    n_lead = sum(1 for r, _ in researched if r["Leadership Roles"])
    n_intl = sum(1 for r, _ in researched if r["International Training"])
    n_multi = sum(1 for r, _ in researched if r["Multiple Practice Locations"])
    n_vol = sum(1 for r, _ in researched if r["Estimated Private Patient Volume"])
    n_fo = sum(1 for r, _ in researched if r["Potential Family Office Fit"])
    n_pms = sum(1 for r, _ in researched if r["Potential PMS Fit"])
    n_affil = sum(1 for r in rows if r["Affiliation Flag"])
    n_page = sum(1 for r, _ in researched if r["Verification Method"] == VERIFY_PAGE)
    n_search = sum(1 for r, _ in researched if r["Verification Method"] == VERIFY_SEARCH)

    summary = [
        ("RUN SUMMARY", "", True),
        ("Total doctors in source list", total, False),
        ("Total doctors processed (researched)", n_res, False),
        ("Not yet researched (baseline rows)", total - n_res, False),
        ("", "", False),
        ("CONFIDENCE (researched rows)", "", True),
        ("High-confidence matches", bands.get(CONF_HIGH, 0), False),
        ("Medium-confidence matches", bands.get(CONF_MEDIUM, 0), False),
        ("Low-confidence matches", bands.get(CONF_LOW, 0), False),
        ("Unknown / unable to verify", bands.get(CONF_UNKNOWN, 0), False),
        ("", "", False),
        ("CONTACT COVERAGE (researched rows)", "", True),
        ("Doctors with direct professional email", n_email, False),
        ("Doctors with professional phone", n_phone, False),
        ("Doctors with LinkedIn", n_linked, False),
        ("Doctors with appointment links", n_appt, False),
        ("Doctors with at least one Tier-1 direct contact", n_direct, False),
        ("Doctors with official profiles but no direct contact", n_profile_only, False),
        ("Doctors with only indirect contact", n_indirect_only, False),
        ("Doctors with no publicly discoverable contact route at all", n_no_contact, False),
        ("", "", False),
        ("DATA QUALITY", "", True),
        ("Duplicate names detected (distinct names)", len(dup_names), False),
        ("Rows affected by duplicate names", dup_rows, False),
        ("Ambiguous identities requiring manual review", n_ambiguous, False),
        ("Source experience contradicts published profile (>3 yrs)", n_exp_disc, False),
        ("Hospital in source list may be stale/incomplete (notes scan)", n_affil, False),
        ("Rows flagged 'Needs Human Review'", n_review, False),
        ("Total rows on the manual-review sheet", len(review_rows), False),
        ("", "", False),
        ("HNI PROSPECT QUALIFICATION (researched rows)", "", True),
        ("P1 - contact first (score >= 60)", n_p1, False),
        ("P2 (score 40-59)", n_p2, False),
        ("P3 (score 22-39)", n_p3, False),
        ("P4 - insufficient public signal (score < 22)", n_p4, False),
        ("Doctors owning a clinic or practice", n_own, False),
        ("Doctors with a hospital leadership title", n_lead, False),
        ("Doctors with international training/credentials", n_intl, False),
        ("Doctors practising at multiple locations", n_multi, False),
        ("Doctors with a publicly stated procedure volume", n_vol, False),
        ("Potential family-office fit", n_fo, False),
        ("Potential PMS fit", n_pms, False),
        ("", "", False),
        ("VERIFICATION METHOD (researched rows)", "", True),
        ("Page-verified (profile page retrieved and matched)", n_page, False),
        ("Search-verified (search-index evidence only)", n_search, False),
    ]
    ws4 = wb.create_sheet("Summary")
    for j, h in enumerate(("Metric", "Value"), 1):
        c = ws4.cell(row=1, column=j, value=h)
        c.fill = HDR_FILL
        c.font = HDR_FONT
    for i, (label, value, bold) in enumerate(summary, start=2):
        a = ws4.cell(row=i, column=1, value=label)
        b = ws4.cell(row=i, column=2, value=value)
        a.font = Font(bold=bold, size=10)
        b.font = Font(bold=bold, size=10)
        if bold:
            a.fill = PatternFill("solid", fgColor="DDEBF7")
            b.fill = PatternFill("solid", fgColor="DDEBF7")
    ws4.column_dimensions["A"].width = 58
    ws4.column_dimensions["B"].width = 16
    ws4.freeze_panes = "A2"

    # ---- Sheet 5: README ---------------------------------------------------
    readme = [
        ("Doctors_Enriched.xlsx - Doctor Contact Enrichment Engine", True),
        ("", False),
        ("WHAT THIS IS", True),
        ("Every doctor from the source list, enriched with publicly available", False),
        ("professional contact routes found through open-internet OSINT research.", False),
        ("The first 26 columns (lighter blue headers) are the requested enrichment", False),
        ("schema. Columns after them preserve the original source data and the", False),
        ("prospecting enrichment from earlier runs.", False),
        ("", False),
        ("HOW TO READ A ROW", True),
        ("- 'Best Way To Reach' is the single actionable recommendation. Start there.", False),
        ("- Tier 1 (direct): Professional Email > Professional Phone > Appointment Link.", False),
        ("- Tier 2 (official presence): Hospital Profile, Clinic URL, LinkedIn,", False),
        ("  Google Scholar, ResearchGate, ORCID, Professional Website.", False),
        ("- Tier 3: professional social media only.", False),
        ("- 'Indirect Contact Method'/'Details' is the fallback route and is populated", False),
        ("  for EVERY row, so no doctor is a dead end.", False),
        ("", False),
        ("CONFIDENCE SCORE", True),
        ("  High     verified by two or more independent official sources", False),
        ("  Medium   strong evidence but only one official source", False),
        ("  Low      partial match only", False),
        ("  Unknown  unable to confidently verify (includes not-yet-researched rows)", False),
        ("An 'official source' means the hospital's own site, Apollo247, a government", False),
        ("registry, a university/academic domain, ORCID or Google Scholar. Reputable", False),
        ("directories (Practo, Lybrate, Skedoc, HexaHealth) corroborate identity but", False),
        ("do not by themselves earn a High band.", False),
        ("", False),
        ("VERIFICATION METHOD - please read", True),
        ("  Page-verified    the profile page itself was retrieved and matched.", False),
        ("  Search-verified  identity and URLs confirmed from search-index results", False),
        ("                   (title, snippet and URL) only. The environment running", False),
        ("                   this pipeline had a network policy that blocked page", False),
        ("                   fetching for all healthcare domains, so page-level", False),
        ("                   confirmation was not possible for these rows. Treat them", False),
        ("                   as strong evidence but not page-confirmed.", False),
        ("  Not verified     baseline row, no doctor-specific research yet.", False),
        ("", False),
        ("STATUS VALUES", True),
        ("  Enriched                      identity verified, fields backed by sources.", False),
        ("  Ambiguous Match               multiple same-name doctors; contacts withheld.", False),
        ("  Needs Human Review            insufficient public info to verify.", False),
        ("  Baseline (not yet researched)  source data + verified hospital route only.", False),
        ("", False),
        ("ANTI-FABRICATION RULES APPLIED", True),
        ("- No fabrication, no inference, no guessing. Unverifiable fields are blank.", False),
        ("- No URL was ever constructed or pattern-guessed. Every URL appeared", False),
        ("  verbatim in a search result or on a page that was retrieved.", False),
        ("- No email or phone was ever inferred from a name and a domain.", False),
        ("- Only institutional and publicly published professional contacts. No", False),
        ("  personal mobile numbers, no personal email addresses, and nothing from", False),
        ("  private or restricted sources.", False),
        ("- Social profiles included only where clearly used professionally.", False),
        ("- Every populated field is traceable through the 'Sources Used' column.", False),
        ("", False),
        ("TWO SOURCE-DATA WARNINGS", True),
        ("'Experience Discrepancy' flags rows where a hospital's own profile", False),
        ("disagrees with the source list's experience figure by more than 3 years.", False),
        ("That column feeds Priority Rank, so the research queue is partly ordered", False),
        ("on figures the hospitals themselves contradict. Source values are left", False),
        ("exactly as given and never silently corrected.", False),
        ("", False),
        ("'Affiliation Flag' marks rows where research found the doctor may have", False),
        ("moved, may hold a dual appointment, or where the named unit could not be", False),
        ("confirmed. It is a KEYWORD SCAN OF THE RESEARCH NOTES, not a derived", False),
        ("fact - always read the Notes column before contacting these doctors.", False),
        ("Contacting the hospital named in the source list may reach the wrong", False),
        ("institution for them.", False),
        ("", False),
        ("COUNTRY", True),
        ("All eight hospital groups in this list are Hyderabad, India facilities, so", False),
        ("Country is India for every row. That is a fact about the source list, not a", False),
        ("per-doctor research finding.", False),
        ("", False),
        ("PRIORITY RANK / HNI PRIORITY SCORE", True),
        ("A prioritisation heuristic built only from public professional-seniority", False),
        ("signals (years of experience, specialty, hospital affiliation, locality).", False),
        ("It orders the research queue. It is NOT a financial assessment of any", False),
        ("individual's actual wealth.", False),
    ]
    ws5 = wb.create_sheet("README")
    for i, (t, bold) in enumerate(readme, 1):
        c = ws5.cell(row=i, column=1, value=t)
        c.font = Font(bold=bold, size=13 if (bold and i == 1) else 10)
    ws5.column_dimensions["A"].width = 92

    wb.save(OUT)
    print(f"Wrote {OUT}")
    print(f"  {total} doctors | {n_res} researched | {total - n_res} baseline")
    print(f"  confidence: High {bands.get(CONF_HIGH,0)}  "
          f"Medium {bands.get(CONF_MEDIUM,0)}  Low {bands.get(CONF_LOW,0)}  "
          f"Unknown {bands.get(CONF_UNKNOWN,0)}")
    print(f"  direct contact {n_direct} | email {n_email} | phone {n_phone} | "
          f"appt {n_appt} | linkedin {n_linked}")
    print(f"  rows with no contact route at all: {n_no_contact} (must be 0)")
    print(f"  manual review rows: {len(review_rows)}  "
          f"(dup names {len(dup_names)}, ambiguous {n_ambiguous})")


if __name__ == "__main__":
    main()
