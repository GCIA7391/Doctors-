#!/usr/bin/env python3
"""
Resume-safe work queue: what still needs researching, in priority order.

The queue is derived every time from `master_ranked.json` minus whatever result
files already exist, so a session can resume with no bookkeeping and no memory
of which wave ran last. Nothing to reset, nothing to get out of sync.

Usage:
  python3 scripts/next_batch.py                 # progress summary
  python3 scripts/next_batch.py 40              # next 40 doctors, chunked
  python3 scripts/next_batch.py 40 5            # next 40 in chunks of 5
"""
import json, os, sys, glob


def done_row_ids():
    ids = set()
    for p in glob.glob("state/results/row_*.json"):
        base = os.path.basename(p)
        try:
            ids.add(int(base[len("row_"):-len(".json")]))
        except ValueError:
            continue
    return ids


def pending(limit=None):
    recs = json.load(open("state/master_ranked.json"))
    done = done_row_ids()
    rem = [r for r in recs if r["row_id"] not in done]
    return (rem[:limit] if limit else rem), len(recs), len(done)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    chunk = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    rem, total, n_done = pending(limit)
    all_rem, _, _ = pending(None)

    print(f"# progress: {n_done}/{total} researched "
          f"({100.0 * n_done / total:.1f}%), {len(all_rem)} remaining")
    if not rem:
        print("# nothing pending - the whole list is researched")
        return
    print(f"# next {len(rem)} in priority order "
          f"(rank #{rem[0]['priority_rank']} onward)\n")

    for i in range(0, len(rem), chunk):
        print(f"### CHUNK {i // chunk + 1}")
        for d in rem[i:i + chunk]:
            print(f"row_id={d['row_id']} | rank#{d['priority_rank']} | {d['name']} | "
                  f"{d['department']} | {d['experience_raw']} | {d['hospital']} | "
                  f"{d['address']}")
        print()


if __name__ == "__main__":
    main()
