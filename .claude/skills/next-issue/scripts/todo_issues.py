#!/usr/bin/env python3
"""List Todo issues in the OrganizeMe project for a given slice, grouped by priority tier.

The skill uses this to get a deterministic shortlist so it doesn't re-derive the gathering
and tiering logic on every run. It intentionally does NOT make the final pick — the ordering
within a tier is a judgment call (dependencies, what unblocks the most, what makes a good
foundation) that the model makes after reading the candidate issue bodies.

Usage:
    python todo_issues.py                       # defaults to --slice slice1 --status Todo
    python todo_issues.py --slice slice2        # when the project advances to a later slice

Priority tiers (highest first): bug > enhancement > future-enhancement > (other/untiered)
Output: JSON on stdout: {"slice": ..., "status": ..., "tiers": {"bug": [...], ...}}
Each candidate: {"number", "title", "labels"}.
"""
import argparse
import json
import subprocess
import sys

PROJECT_NUMBER = "2"
PROJECT_OWNER = "rustycoopes"

# Highest priority first. An issue is placed in the first tier whose label it carries.
TIER_ORDER = ["bug", "enhancement", "future-enhancement"]


def fetch_items():
    try:
        out = subprocess.run(
            ["gh", "project", "item-list", PROJECT_NUMBER,
             "--owner", PROJECT_OWNER, "--format", "json", "--limit", "300"],
            capture_output=True, text=True, check=True,
        ).stdout
    except FileNotFoundError:
        sys.exit("error: `gh` CLI not found on PATH.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: gh project item-list failed:\n{e.stderr}")
    return json.loads(out).get("items", [])


def classify(labels):
    for tier in TIER_ORDER:
        if tier in labels:
            return tier
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default="slice1",
                    help="slice label to filter by (default: slice1 — the slice in progress)")
    ap.add_argument("--status", default="Todo",
                    help="project Status value to filter by (default: Todo)")
    args = ap.parse_args()

    tiers = {t: [] for t in TIER_ORDER + ["other"]}
    for item in fetch_items():
        content = item.get("content") or {}
        number = content.get("number")
        if number is None:  # draft items with no linked issue
            continue
        if (item.get("status") or "") != args.status:
            continue
        labels = item.get("labels") or []
        if args.slice not in labels:
            continue
        tiers[classify(labels)].append({
            "number": number,
            "title": content.get("title", ""),
            "labels": labels,
        })

    for t in tiers:
        tiers[t].sort(key=lambda c: c["number"])

    total = sum(len(v) for v in tiers.values())
    print(json.dumps({
        "slice": args.slice,
        "status": args.status,
        "total": total,
        "tiers": tiers,
    }, indent=2))


if __name__ == "__main__":
    main()
