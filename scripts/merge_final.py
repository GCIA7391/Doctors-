#!/usr/bin/env python3
"""
Merge ALL enrichment results into Doctors_Enriched.xlsx.

- Sheet 1 "Enriched Doctors": every doctor (priority order), enriched where a
  result exists, otherwise marked "Not yet processed".
- Sheet 2 "Priority (HNI) Ranking": compact prospecting view sorted by priority,
  showing only processed doctors with key contact/profile fields.
- Sheet 3 "README": methodology, column meanings, confidence rubric, caveats.

Usage: python3 scripts/merge_final.py
"""
import json, os, sys, glob
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
sys.path.insert(0, os.path.dirname(__file__))
from schema import OUTPUT_COLUMNS, RESULT_KEY_TO_COLUMN

HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def load_result(row_id):
    p = f"state/results/row_{row_id}.json"
    return json.load(open(p)) if os.path.exists(p) else None

def build_row(rec, res):
    row = {c: "" for c in OUTPUT_COLUMNS}
    row["Doctor Name"] = rec["name"]; row["Department"] = rec["department"]
    row["Experience"] = rec["experience_raw"]; row["Hospital"] = rec["hospital"]
    row["Address"] = rec["address"]; row["City"] = rec.get("city_guess","")
    row["Priority Rank"] = rec["priority_rank"]; row["HNI Priority Score"] = rec["priority_score"]
    if res:
        for k, col in RESULT_KEY_TO_COLUMN.items():
            v = res.get(k, "")
            if isinstance(v, bool): v = "Yes" if v else ""
            row[col] = v if v is not None else ""
        if res.get("city"): row["City"] = res["city"]
    else:
        row["Status"] = "Not yet processed"
    return row

def style_header(ws, cols):
    for j, col in enumerate(cols, 1):
        c = ws.cell(row=1, column=j, value=col)
        c.fill = HDR_FILL; c.font = HDR_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    ws.freeze_panes = "A2"; ws.row_dimensions[1].height = 42

def conf_fill(v):
    try: v = float(v)
    except (TypeError, ValueError): return None
    if v >= 90: return PatternFill("solid", fgColor="C6EFCE")
    if v >= 80: return PatternFill("solid", fgColor="FFEB9C")
    if v > 0:  return PatternFill("solid", fgColor="FFC7CE")
    return None

def main():
    recs = json.load(open("state/master_ranked.json"))
    wb = openpyxl.Workbook()

    # ---- Sheet 1: full enriched ----
    ws = wb.active; ws.title = "Enriched Doctors"
    style_header(ws, OUTPUT_COLUMNS)
    conf_idx = OUTPUT_COLUMNS.index("Confidence Score") + 1
    processed = 0
    for i, rec in enumerate(recs, start=2):
        res = load_result(rec["row_id"])
        if res: processed += 1
        row = build_row(rec, res)
        for j, col in enumerate(OUTPUT_COLUMNS, 1):
            c = ws.cell(row=i, column=j, value=row[col])
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = BORDER; c.font = Font(size=9)
        f = conf_fill(row["Confidence Score"])
        if f: ws.cell(row=i, column=conf_idx).fill = f
    widths = {"Doctor Name":24,"Department":22,"Experience":11,"Hospital":18,
              "Address":30,"City":16,"Priority Rank":8,"HNI Priority Score":9,
              "Sources":50,"Notes":40,"HNI Signals":34,"Verified Role/Title":26,"Status":18}
    for j, col in enumerate(OUTPUT_COLUMNS, 1):
        ws.column_dimensions[get_column_letter(j)].width = widths.get(col, 24)

    # ---- Sheet 2: prospecting view (processed only) ----
    ws2 = wb.create_sheet("Priority (HNI) Ranking")
    pcols = ["Priority Rank","HNI Priority Score","Doctor Name","Department",
             "Hospital","City","Verified Role/Title","Owns Clinic/Practice",
             "HNI Signals","Official Hospital Profile","Practo Profile","LinkedIn URL",
             "Appointment Number","Hospital Number","Professional Email",
             "Confidence Score","Status"]
    style_header(ws2, pcols)
    r = 2
    for rec in recs:
        res = load_result(rec["row_id"])
        if not res: continue
        full = build_row(rec, res)
        for j, col in enumerate(pcols, 1):
            c = ws2.cell(row=r, column=j, value=full[col])
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = BORDER; c.font = Font(size=9)
        f = conf_fill(full["Confidence Score"])
        if f: ws2.cell(row=r, column=len(pcols)-1).fill = f
        r += 1
    w2 = {"Priority Rank":8,"HNI Priority Score":9,"Doctor Name":24,"Department":22,
          "Hospital":18,"City":16,"Verified Role/Title":28,"Owns Clinic/Practice":10,
          "HNI Signals":38,"Official Hospital Profile":40,"Practo Profile":36,
          "LinkedIn URL":32,"Appointment Number":18,"Hospital Number":18,
          "Professional Email":26,"Confidence Score":10,"Status":18}
    for j, col in enumerate(pcols, 1):
        ws2.column_dimensions[get_column_letter(j)].width = w2.get(col, 22)

    # ---- Sheet 3: README ----
    ws3 = wb.create_sheet("README")
    readme = [
        ("Doctors_Enriched.xlsx — OSINT enrichment", True),
        ("", False),
        ("Purpose: prospecting list of Hyderabad hospital doctors, prioritised by", False),
        ("likelihood of being high-net-worth individuals (HNIs), enriched with", False),
        ("PUBLIC professional information only.", False),
        ("", False),
        ("METHODOLOGY", True),
        ("- Doctors ranked by an 'HNI Priority Score' (0-100) built ONLY from public", False),
        ("  professional-seniority signals: years of experience, high-fee specialty,", False),
        ("  premium-hospital affiliation, Hyderabad locality. This is a prioritisation", False),
        ("  heuristic, NOT a financial assessment of any individual's actual wealth.", False),
        ("- Each doctor researched via official hospital sites, Practo, Apollo247,", False),
        ("  LinkedIn, ResearchGate, Google Scholar and reputable directories.", False),
        ("- Every populated field is backed by a source URL in the 'Sources' column.", False),
        ("", False),
        ("GOLDEN RULES APPLIED", True),
        ("- No fabrication, no inference, no guessing. Unverifiable fields left blank.", False),
        ("- Only institutional/public contacts (appointment/clinic/hospital/secretary,", False),
        ("  officially published emails). No private mobile numbers or personal emails.", False),
        ("- Social profiles included only when unambiguously the doctor's.", False),
        ("", False),
        ("CONFIDENCE SCORE (0-100)", True),
        ("  Identity 40 + Hospital 20 + Department 15 + Location 10 +", False),
        ("  Publications/Employment 10 + Other 5.", False),
        ("  Green >=90 (high) | Yellow 80-89 (moderate) | Red <80 (treat as partial).", False),
        ("", False),
        ("STATUS VALUES", True),
        ("  Enriched            = identity verified, fields backed by sources.", False),
        ("  Ambiguous Match     = multiple same-name doctors; contacts withheld.", False),
        ("  Needs Human Review  = insufficient public info to verify confidently.", False),
        ("  Not yet processed   = queued, not yet researched in this run.", False),
    ]
    for i,(t,bold) in enumerate(readme,1):
        c = ws3.cell(row=i, column=1, value=t)
        c.font = Font(bold=bold, size=12 if (bold and i==1) else 10)
    ws3.column_dimensions["A"].width = 90

    wb.save("Doctors_Enriched.xlsx")
    total = len(recs)
    print(f"Wrote Doctors_Enriched.xlsx: {total} doctors, {processed} enriched, "
          f"{total-processed} pending ({100*processed/total:.1f}% done)")

if __name__ == "__main__":
    main()
