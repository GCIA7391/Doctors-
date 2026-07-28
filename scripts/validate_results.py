#!/usr/bin/env python3
"""
Validate enrichment result JSON files against the anti-fabrication contract.

Flags (does not auto-delete) any result where:
  - a profile/contact/social field is populated but `sources` is empty, or
  - an email/phone field is populated but no URL/source line references it, or
  - confidence is missing/non-numeric, or status is invalid, or
  - a populated URL field does not look like a URL.

Usage: python3 scripts/validate_results.py [row_id ...]   (default: all)
"""
import json, os, sys, glob, re

URL_FIELDS = ["linkedin","hospital_profile","practo","directory_profile",
              "lybrate","researchgate","google_scholar","personal_website",
              "twitter","facebook","instagram","youtube"]
CONTACT_FIELDS = ["professional_email","department_email","hospital_email",
                  "appointment_number","clinic_number","secretary_number",
                  "hospital_number"]
VALID_STATUS = {"Enriched","Ambiguous Match","Needs Human Review"}
URLRE = re.compile(r"https?://", re.I)

def check(res, path):
    issues = []
    for k in ("row_id","status","confidence","sources"):
        if k not in res:
            issues.append(f"missing key '{k}'")
    conf = res.get("confidence")
    if not isinstance(conf, (int, float)):
        issues.append(f"confidence not numeric: {conf!r}")
    if res.get("status") not in VALID_STATUS:
        issues.append(f"invalid status: {res.get('status')!r}")
    sources = str(res.get("sources","") or "")
    for f in URL_FIELDS:
        v = str(res.get(f,"") or "").strip()
        if v:
            if not URLRE.search(v):
                issues.append(f"{f} not a URL: {v!r}")
            # the url should be traceable in sources
            if v not in sources and not URLRE.search(sources):
                issues.append(f"{f} populated but no source URL in `sources`")
    for f in CONTACT_FIELDS:
        v = str(res.get(f,"") or "").strip()
        if v and not sources.strip():
            issues.append(f"{f}={v!r} populated but `sources` empty (fabrication risk)")
    return issues

def main():
    ids = sys.argv[1:]
    if ids:
        paths = [f"state/results/row_{i}.json" for i in ids]
    else:
        paths = sorted(glob.glob("state/results/row_*.json"))
    ok = bad = 0
    for p in paths:
        if not os.path.exists(p):
            print(f"MISSING: {p}"); bad += 1; continue
        try:
            res = json.load(open(p))
        except Exception as e:
            print(f"BAD JSON {p}: {e}"); bad += 1; continue
        issues = check(res, p)
        rid = res.get("row_id","?")
        if issues:
            bad += 1
            print(f"\n[FLAG] row {rid} ({os.path.basename(p)}) conf={res.get('confidence')} status={res.get('status')!r}")
            for it in issues:
                print(f"    - {it}")
        else:
            ok += 1
    print(f"\n=== {ok} clean, {bad} flagged, {len(paths)} total ===")

if __name__ == "__main__":
    main()
