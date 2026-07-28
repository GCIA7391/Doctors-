#!/usr/bin/env python3
"""Print compact per-chunk doctor assignments for dispatching research agents.
Usage: python3 scripts/emit_chunks.py <batch_no> [batch_size=25] [chunk=5]"""
import json, sys
bn = int(sys.argv[1]); size = int(sys.argv[2]) if len(sys.argv)>2 else 25
ch = int(sys.argv[3]) if len(sys.argv)>3 else 5
recs = json.load(open("state/master_ranked.json"))
sl = recs[(bn-1)*size:(bn-1)*size+size]
for i in range(0, len(sl), ch):
    chunk = sl[i:i+ch]
    print(f"### CHUNK {i//ch+1}")
    for d in chunk:
        print(f"row_id={d['row_id']} | {d['name']} | {d['department']} | "
              f"{d['experience_raw']} | {d['hospital']} | {d['address']}")
    print()
