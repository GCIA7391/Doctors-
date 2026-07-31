#!/usr/bin/env python3
"""
Post-wave checkpoint: validate everything, rebuild the deliverable, commit.

Run after each wave of research agents finishes. Safe to run repeatedly; if
nothing changed it says so and makes no commit.

Usage:
  python3 scripts/checkpoint.py                  # validate, rebuild, commit
  python3 scripts/checkpoint.py --no-commit      # validate and rebuild only
  python3 scripts/checkpoint.py -m "wave 3"      # custom commit message suffix
"""
import json, os, subprocess, sys, glob, re


def run(cmd, check=True):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and p.returncode != 0:
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {cmd}")
    return p


def progress():
    recs = json.load(open("state/master_ranked.json"))
    done = len(glob.glob("state/results/row_*.json"))
    return done, len(recs)


def main():
    suffix = ""
    if "-m" in sys.argv:
        suffix = sys.argv[sys.argv.index("-m") + 1]
    commit = "--no-commit" not in sys.argv

    print("=== validating results ===")
    v = run("python3 scripts/validate_results.py", check=False)
    tail = v.stdout.strip().splitlines()[-1] if v.stdout.strip() else ""
    print(v.stdout[-4000:] if len(v.stdout) > 4000 else v.stdout)
    m = re.search(r"(\d+) clean, (\d+) warned, (\d+) flagged", tail)
    flagged = int(m.group(3)) if m else -1
    if flagged > 0:
        print(f"\n!! {flagged} result(s) flagged. Fix them before checkpointing; "
              f"the deliverable was NOT rebuilt.")
        raise SystemExit(1)

    print("=== rebuilding deliverable ===")
    merged = run("python3 scripts/merge_final.py").stdout
    print(merged)

    # Take the count from the rebuild itself. Agents may still be writing into
    # state/results/, so re-globbing here would report a number that disagrees
    # with the workbook we just wrote.
    m = re.search(r"(\d+) doctors \| (\d+) researched", merged)
    if m:
        total, done = int(m.group(1)), int(m.group(2))
    else:
        done, total = progress()
    if not commit:
        print(f"(skipping commit) {done}/{total} researched")
        return

    if not run("git status --porcelain", check=False).stdout.strip():
        print("nothing changed - no commit made")
        return

    msg = (f"Enrichment checkpoint: {done}/{total} doctors researched "
           f"({100.0 * done / total:.1f}%)")
    if suffix:
        msg += f" - {suffix}"
    body = (f"{msg}\n\n"
            f"Validated with scripts/validate_results.py (0 flagged) and "
            f"regenerated Doctors_Enriched.xlsx.\n\n"
            f"Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            f"Claude-Session: https://claude.ai/code/session_01AZSjukLSp8Yj2qWjw5e9Uf")
    run("git add -A")
    subprocess.run(["git", "commit", "-q", "-m", body], check=True)
    print(run("git log --oneline -1").stdout.strip())


if __name__ == "__main__":
    main()
