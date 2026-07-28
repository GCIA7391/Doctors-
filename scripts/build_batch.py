#!/usr/bin/env python3
"""
Emit the input slice for a batch of doctors (in priority order) as JSON, and
create the per-doctor result directory. Usage: python3 scripts/build_batch.py <batch_no> [size]
"""
import json, os, sys, re

HYD_LOCALITIES = [
    "hyderabad","secunderabad","jubilee hills","banjara hills","gachibowli",
    "financial district","kondapur","madhapur","hitec city","hitech city",
    "kukatpally","manikonda","hyderguda","somajiguda","begumpet","malakpet",
]

def city_of(addr):
    a = str(addr or "").lower()
    if "secunderabad" in a: return "Secunderabad (Hyderabad)"
    if any(l in a for l in HYD_LOCALITIES): return "Hyderabad"
    return ""  # unknown -> leave for enrichment

def main():
    batch_no = int(sys.argv[1])
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    with open("state/master_ranked.json") as f:
        recs = json.load(f)
    start = (batch_no - 1) * size
    slice_ = recs[start:start + size]
    for r in slice_:
        r["city_guess"] = city_of(r["address"])
    os.makedirs(f"state/results", exist_ok=True)
    out = f"state/batch_{batch_no:03d}_input.json"
    with open(out, "w") as f:
        json.dump(slice_, f, indent=2, ensure_ascii=False)
    print(f"Batch {batch_no}: doctors #{start+1}-{start+len(slice_)} -> {out}")
    for r in slice_:
        print(f"  row_id={r['row_id']:4d} rank#{r['priority_rank']:4d} | "
              f"{r['name'][:34]:34s} | {r['department'][:24]:24s} | {r['hospital']}")

if __name__ == "__main__":
    main()
