#!/usr/bin/env python3
"""
Build a priority-ranked master list of doctors for OSINT enrichment.

Priority = "HNI likelihood" heuristic for a Hyderabad capital-advisory firm.
This is a PRIORITIZATION heuristic built ONLY from public professional-seniority
signals (years of experience, high-earning specialty, premium-hospital affiliation).
It is NOT a financial assessment of any individual's actual wealth.

Output: state/master_ranked.json  (stable row ids, ordering, preliminary score)
"""
import openpyxl, json, re, os

SRC = "data/source_Consolidated_Doctor_Names_List.xlsx"

# High-earning / high-fee private-practice specialties (revenue heuristic, not a
# judgement about individuals). Weight 0-10.
SPECIALTY_WEIGHT = {
    # top tier
    "cardiology": 10, "cardiac surgery": 10, "ctvs": 10, "cardiothoracic": 10,
    "cardiac sciences": 10,
    "oncology": 10, "medical oncology": 10, "surgical oncology": 10,
    "radiation oncology": 10, "hemato": 10, "haemato": 10,
    "neurosurgery": 10, "neuro surgery": 10, "neurosciences": 9, "neurology": 9,
    "orthopedic": 9, "orthopaedic": 9, "orthopedics": 9, "joint replacement": 10,
    "spine": 9,
    "plastic": 9, "cosmetic": 9, "aesthetic": 9,
    "urology": 9, "uro": 8,
    "gastroenterology": 9, "surgical gastroenterology": 9, "hepatology": 9,
    "hpb": 9, "liver": 9, "transplant": 10,
    "nephrology": 8,
    "reproductive": 9, "ivf": 9, "fertility": 9, "infertility": 9,
    "endocrinology": 8, "endocrine": 8,
    "bariatric": 9,
    # high
    "ophthalmology": 8, "ophthalmic": 8, "eye": 8, "retina": 8,
    "ent": 7, "otorhinolaryngology": 7,
    "pulmonology": 7, "respiratory": 7,
    "dermatology": 8, "dermato": 8,
    "radiology": 7, "interventional radiology": 8, "imaging": 7,
    "rheumatology": 7,
    "vascular": 8,
    "gynecology": 7, "gynaecology": 7, "obstetrics": 7, "obg": 7,
    "general surgery": 7, "gi surgery": 8, "laparoscopic": 7,
    # medium
    "internal medicine": 6, "general medicine": 6, "physician": 6,
    "pediatric": 6, "paediatric": 6, "neonatology": 6,
    "diabetology": 7,
    "gastro": 8,
    "hematology": 9,
    "psychiatry": 6, "psychology": 5,
    "pain": 6,
    "anesthesi": 5, "anaesthesi": 5,
    "critical care": 5, "emergency": 5, "intensive": 5,
    "pathology": 5, "microbiology": 4, "biochemistry": 4,
    "physiotherapy": 3, "physical medicine": 4, "rehab": 4,
    "dental": 6, "dentistry": 6, "maxillofacial": 7,
    "family medicine": 5,
    "nuclear medicine": 6,
    "transfusion": 4,
}

# Premium private-hospital groups in Hyderabad (all roughly comparable tier).
HOSPITAL_WEIGHT = {
    "apollo": 6, "aig": 6, "yashoda": 6, "care": 6, "rainbow": 5,
    "gleneagles": 6, "aware": 5, "citi neuro": 6, "star": 5,
}

HYD_LOCALITIES = [
    "hyderabad","secunderabad","jubilee hills","banjara hills","gachibowli",
    "financial district","kondapur","madhapur","hitec city","hitech city",
    "kukatpally","manikonda","hyderguda","somajiguda","begumpet","malakpet",
    "nampally","dilsukhnagar","attapur","kanchanbagh","tolichowki","mehdipatnam",
    "sainikpuri","nacharam","lb nagar","l b nagar","miyapur","uppal","ameerpet",
    "sarojini","srinagar colony","road no","langar houz","malkajgiri","alwal",
    "kachiguda","narayanguda","himayatnagar","karkhana","habsiguda","kompally",
    "nizampet","chanda nagar","chandanagar","bachupally","shamshabad","kokapet",
    "nallagandla","tellapur",
]

def exp_years(s):
    if not s: return None
    m = re.search(r'(\d+)', str(s))
    return int(m.group(1)) if m else None

def specialty_weight(dept):
    d = str(dept or "").lower()
    best = 0
    for k, w in SPECIALTY_WEIGHT.items():
        if k in d:
            best = max(best, w)
    return best  # 0 if unknown

def hospital_weight(comp):
    c = str(comp or "").lower()
    for k, w in HOSPITAL_WEIGHT.items():
        if k in c:
            return w
    return 3  # other/unknown private

def is_hyderabad(addr):
    a = str(addr or "").lower()
    return any(loc in a for loc in HYD_LOCALITIES)

def priority_score(exp, dept, comp, addr):
    """Preliminary 0-100 ordering score. Refined later with web evidence."""
    # Experience component (0-40). Missing -> neutral-low (12) so it doesn't
    # dominate; seniority gets confirmed during enrichment.
    if exp is None:
        exp_c = 12
    else:
        exp_c = min(40, exp * 1.15)
    # Specialty (0-35)
    spec_c = specialty_weight(dept) * 3.5
    # Hospital tier (0-15)
    hosp_c = hospital_weight(comp) * 2.5
    # Hyderabad locality bonus (0-10)
    loc_c = 10 if is_hyderabad(addr) else 4
    return round(exp_c + spec_c + hosp_c + loc_c, 1)

def main():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    ws = wb["Total Doctors List"]
    recs = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
        name = row[0]
        if not name:
            continue
        exp = exp_years(row[2])
        rec = {
            "row_id": i + 2,               # original spreadsheet row number
            "name": str(name).strip(),
            "department": str(row[1] or "").strip(),
            "experience_raw": str(row[2] or "").strip(),
            "experience_years": exp,
            "hospital": str(row[3] or "").strip(),
            "address": str(row[4] or "").strip(),
            "lead_type": str(row[5] or "").strip(),
            "lead_source": str(row[6] or "").strip(),
            "is_hyderabad": is_hyderabad(row[4]),
            "priority_score": priority_score(exp, row[1], row[3], row[4]),
        }
        recs.append(rec)
    # stable ordering: score desc, then experience desc, then row_id
    recs.sort(key=lambda r: (-r["priority_score"],
                             -(r["experience_years"] or 0),
                             r["row_id"]))
    for rank, r in enumerate(recs, 1):
        r["priority_rank"] = rank
    os.makedirs("state", exist_ok=True)
    with open("state/master_ranked.json", "w") as f:
        json.dump(recs, f, indent=2, ensure_ascii=False)
    print(f"Ranked {len(recs)} doctors -> state/master_ranked.json")
    print("\nTop 20 by priority:")
    for r in recs[:20]:
        print(f"  #{r['priority_rank']:4d} score={r['priority_score']:5.1f} "
              f"exp={str(r['experience_years']):>4} | {r['name'][:32]:32s} | "
              f"{r['department'][:22]:22s} | {r['hospital']}")
    print("\nScore distribution:")
    import collections
    b = collections.Counter()
    for r in recs:
        s = r["priority_score"]
        b[int(s//10)*10]+=1
    for k in sorted(b, reverse=True):
        print(f"  {k:3d}-{k+9}: {b[k]}")

if __name__ == "__main__":
    main()
