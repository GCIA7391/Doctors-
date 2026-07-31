# Doctor Contact Enrichment Engine

An OSINT pipeline that enriches a list of 1,756 Hyderabad hospital doctors with
**publicly available professional contact routes**, and guarantees that every
row ends up with at least one legitimate way to reach the person.

Deliverable: **`Doctors_Enriched.xlsx`**

---

## Resuming work (read this first)

The work queue is computed fresh every time from
`state/master_ranked.json` minus whatever result files exist in
`state/results/`. There is no cursor, no wave counter, nothing to reset.

```bash
pip install openpyxl                    # only third-party dependency

python3 scripts/next_batch.py           # how far along are we?
python3 scripts/next_batch.py 40 5      # next 40 doctors, in chunks of 5
```

Then dispatch a research agent per chunk, each one told to read
`scripts/AGENT_INSTRUCTIONS.md` and write
`state/results/row_<row_id>.json` per doctor. When the wave finishes:

```bash
python3 scripts/checkpoint.py -m "wave N"   # validate -> rebuild xlsx -> commit
```

`checkpoint.py` refuses to rebuild if the validator flags anything, so a bad
result cannot reach the deliverable.

---

## Environment constraint that shapes everything

The environment this pipeline last ran in enforces a dev-infrastructure egress
allowlist. **`WebFetch` and `curl` return HTTP 403 for every healthcare,
directory, academic and social domain** — apollohospitals.com, apollo247.com,
practo.com, yashodahospitals.com, aighospitals.com, carehospitals.com,
linkedin.com, orcid.org, scholar.google.com, researchgate.net, even
wikipedia.org. Only github.com and pypi.org answer.

`WebSearch` works, because it runs server-side.

So research is **search-index-only**: identity and URLs are confirmed from
result titles, snippets and URLs, and a page can never be opened to confirm
itself. Every row records which regime produced it in **`Verification Method`**:

| Value | Meaning |
|---|---|
| `Page-verified` | The profile page was retrieved and matched (earlier runs, when egress was open). |
| `Search-verified` | Identity and URLs confirmed from search-index evidence only. |
| `Not verified` | Baseline row — no doctor-specific research yet. |

If egress is later widened, `Search-verified` rows are the natural re-verification
queue: re-run each row's searches, open the recorded URLs, and upgrade.

---

## Anti-fabrication contract

Enforced by `scripts/validate_results.py`, which is the gate between research
and the deliverable:

- No fabrication, no inference, no guessing. Unverifiable → blank.
- No URL is ever constructed or pattern-guessed. Every URL appeared verbatim in
  a search result.
- No email or phone is ever derived from a name plus a domain.
- Institutional and published contacts only — no personal mobiles, no private
  emails, nothing from restricted sources.
- Every populated field needs a `field: URL` provenance line in `sources`, where
  the URL is the page the value was found **on**.
- A row marked `Ambiguous Match` must carry no contact or profile fields.

---

## Confidence bands

| Band | Meaning |
|---|---|
| `High` | Two or more independent **official** sources agree |
| `Medium` | Strong evidence but only one official source |
| `Low` | Partial match only |
| `Unknown` | Unable to confidently verify (includes not-yet-researched rows) |

*Official* = the hospital's own site, Apollo247, a government registry
(`.gov.in`, NMC/TSMC), a university/academic domain, ORCID, Google Scholar.
*Corroborating only* = Practo, Lybrate, Skedoc, HexaHealth, JustDial, MyUpchar,
Vaidam, ResearchGate, Doximity — never enough alone for `High`.

---

## Layout

```
data/source_Consolidated_Doctor_Names_List.xlsx   original input (never modified)
state/master_ranked.json                          1756 doctors, stable row ids + priority
state/hospital_contacts.json                      verified per-hospital indirect routes
state/results/row_<id>.json                       one raw research record per doctor
Doctors_Enriched.xlsx                             the deliverable
scripts/
  rank.py                 builds master_ranked.json - DO NOT re-run (row ids must stay stable)
  next_batch.py           resume-safe work queue
  AGENT_INSTRUCTIONS.md   the research brief agents follow
  schema.py               canonical column + result-key contract
  derive_fields.py        deterministic derivation of the output columns
  validate_results.py     anti-fabrication gate
  merge_final.py          builds Doctors_Enriched.xlsx
  checkpoint.py           validate -> rebuild -> commit
  build_batch.py, emit_chunks.py, write_batch_xlsx.py   per-batch helpers
```

`state/results/*.json` are the raw audit record and are **never rewritten** by
the pipeline. The output columns are *derived* from them at merge time by
`derive_fields.py`, so the mapping stays reproducible and reviewable.

---

## Workbook sheets

1. **Enriched Doctors** — all 1,756 rows. First 26 columns are the requested
   enrichment schema; the rest preserve source data and prior prospecting work.
2. **Direct Contacts** — only doctors with a Tier-1 direct route.
3. **Duplicates & Manual Review** — same-name collisions, ambiguous identities,
   Low-confidence partial matches.
4. **Summary** — run statistics.
5. **README** — methodology and caveats, in-workbook.

## Scope note

The `Priority Rank` / `HNI Priority Score` columns order the research queue using
only public professional-seniority signals (years of experience, specialty,
hospital affiliation, locality). They are a prioritisation heuristic, **not** a
financial assessment of any individual.
