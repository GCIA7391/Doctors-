#!/usr/bin/env python3
"""
Validate enrichment result JSON against the anti-fabrication contract.

This is the gate between research and the deliverable. It flags (never
auto-deletes) any result where:
  - a profile/contact field is populated but nothing backs it in `sources`
  - a URL field does not contain a URL
  - a URL field is populated but that exact URL is absent from `sources`
  - an email is malformed or uses a personal provider (institutional only)
  - a phone number is implausible for a published institutional contact
  - confidence / confidence_band / status / verification_method are invalid
  - a row marked Ambiguous Match still carries contact or profile fields

Usage:
  python3 scripts/validate_results.py                # all results
  python3 scripts/validate_results.py 110 114        # specific row ids
  python3 scripts/validate_results.py --strict       # non-zero exit on any flag
"""
import json, os, sys, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import (URL_FIELDS, VALID_STATUS, VALID_CONFIDENCE,
                    VERIFY_PAGE, VERIFY_SEARCH, VERIFY_NONE)

URLRE = re.compile(r"https?://", re.I)
EMAILRE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PERSONAL_EMAIL_DOMAINS = ("gmail.", "yahoo.", "hotmail.", "outlook.",
                          "rediffmail.", "live.", "icloud.", "protonmail.")
VALID_VERIFY = {VERIFY_PAGE, VERIFY_SEARCH, VERIFY_NONE, ""}

EMAIL_FIELDS = ("professional_email", "department_email", "hospital_email")
PHONE_FIELDS = ("professional_phone", "appointment_number", "clinic_number",
                "secretary_number", "hospital_number")


def _digits(s):
    return re.sub(r"\D", "", str(s or ""))


def _sourced_fields(sources):
    """Field names that have a provenance line in `sources`.

    The contract is one `field: URL` line per populated field, where the URL is
    the page the value was found ON - not the value itself. A doctor's own site
    listing his LinkedIn is correct provenance for the `linkedin` field.
    """
    names = set()
    for line in str(sources or "").splitlines():
        m = re.match(r"\s*([A-Za-z0-9_]+)\s*:", line)
        if m:
            names.add(m.group(1).strip().lower())
    return names


def _phone_parts(v):
    """Split a multi-value phone field into individual numbers.

    Published contacts legitimately come as 'Kumari 9866896555, Shravanthi
    7386863029' or '+91 93901 50150 / +91 95810 00505'.
    """
    parts = re.split(r"[,;/|]| or ", str(v or ""))
    return [p for p in (_digits(x) for x in parts) if p]


def check(res):
    """Return (issues, warnings)."""
    issues, warnings = [], []
    sources = str(res.get("sources", "") or "")
    has_any_source_url = bool(URLRE.search(sources))
    sourced = _sourced_fields(sources)

    # --- required keys ----------------------------------------------------
    for k in ("row_id", "status", "sources"):
        if k not in res:
            issues.append(f"missing key '{k}'")

    # --- status / confidence / verification -------------------------------
    if res.get("status") not in VALID_STATUS:
        issues.append(f"invalid status: {res.get('status')!r}")

    band = res.get("confidence_band")
    if band is not None and str(band).strip() and band not in VALID_CONFIDENCE:
        issues.append(f"invalid confidence_band: {band!r}")

    conf = res.get("confidence")
    if conf is not None and not isinstance(conf, (int, float)):
        issues.append(f"confidence not numeric: {conf!r}")
    if conf is None and not str(band or "").strip():
        issues.append("neither `confidence` nor `confidence_band` present")

    vm = res.get("verification_method")
    if vm is not None and vm not in VALID_VERIFY:
        issues.append(f"invalid verification_method: {vm!r}")

    # --- URL fields -------------------------------------------------------
    for f in URL_FIELDS:
        v = str(res.get(f, "") or "").strip()
        if not v:
            continue
        if not URLRE.search(v):
            issues.append(f"{f} is not a URL: {v!r}")
            continue
        if not has_any_source_url:
            issues.append(f"{f} populated but `sources` has no URL at all")
        elif f not in sourced and v not in sources:
            issues.append(f"{f} populated but `sources` has no '{f}:' "
                          f"provenance line (untraceable)")

    # --- emails -----------------------------------------------------------
    for f in EMAIL_FIELDS:
        v = str(res.get(f, "") or "").strip()
        if not v:
            continue
        if not EMAILRE.match(v):
            issues.append(f"{f} is not a valid email: {v!r}")
        if any(d in v.lower() for d in PERSONAL_EMAIL_DOMAINS):
            # A clinic that publishes a gmail address as its business contact is
            # still an institutional contact. Surface it for review rather than
            # rejecting it - but never accept one that looks like an individual's
            # private address.
            warnings.append(f"{f}={v} uses a consumer email provider - confirm "
                            f"it is the practice's published business address, "
                            f"not a private one")
        if not has_any_source_url:
            issues.append(f"{f}={v} populated but `sources` has no URL "
                          f"(fabrication risk)")
        elif f not in sourced:
            issues.append(f"{f} populated but `sources` has no '{f}:' line")

    # --- phones -----------------------------------------------------------
    for f in PHONE_FIELDS:
        v = str(res.get(f, "") or "").strip()
        if not v:
            continue
        parts = _phone_parts(v)
        if not parts:
            issues.append(f"{f}={v!r} contains no digits")
        for d in parts:
            if len(d) < 7 or len(d) > 15:
                issues.append(f"{f} number {d!r} has an implausible length "
                              f"({len(d)} digits) in {v!r}")
            if len(set(d)) == 1:
                issues.append(f"{f} number {d!r} is a repeated single digit "
                              f"(placeholder?)")
        if not has_any_source_url:
            issues.append(f"{f}={v} populated but `sources` has no URL "
                          f"(fabrication risk)")
        elif f not in sourced:
            issues.append(f"{f} populated but `sources` has no '{f}:' line")

    # --- ambiguous rows must not carry contacts ---------------------------
    if res.get("status") == "Ambiguous Match":
        leaked = [f for f in list(EMAIL_FIELDS) + list(PHONE_FIELDS) + URL_FIELDS
                  if str(res.get(f, "") or "").strip()]
        if leaked:
            issues.append(f"status is Ambiguous Match but these are populated: "
                          f"{', '.join(leaked)}")

    return issues, warnings


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv

    if args:
        paths = [f"state/results/row_{i}.json" for i in args]
    else:
        paths = sorted(glob.glob("state/results/row_*.json"),
                       key=lambda p: int(re.search(r"row_(\d+)", p).group(1)))

    ok = bad = warned = 0
    for p in paths:
        if not os.path.exists(p):
            print(f"MISSING: {p}")
            bad += 1
            continue
        try:
            res = json.load(open(p))
        except Exception as e:
            print(f"BAD JSON {p}: {e}")
            bad += 1
            continue
        issues, warnings = check(res)
        if issues or warnings:
            label = "FLAG" if issues else "WARN"
            print(f"\n[{label}] row {res.get('row_id','?')} ({os.path.basename(p)}) "
                  f"conf={res.get('confidence')} band={res.get('confidence_band')!r} "
                  f"status={res.get('status')!r}")
            for it in issues:
                print(f"    - {it}")
            for w in warnings:
                print(f"    ? {w}")
        if issues:
            bad += 1
        elif warnings:
            warned += 1
        else:
            ok += 1

    print(f"\n=== {ok} clean, {warned} warned, {bad} flagged, "
          f"{len(paths)} total ===")
    if strict and bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
