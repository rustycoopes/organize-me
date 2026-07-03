#!/usr/bin/env python3
"""List Todo issues in the OrganizeMe project, grouped by slice number then priority tier.

The skill uses this to get a deterministic shortlist so it doesn't re-derive the gathering,
slice-ordering, and tiering logic on every run. It intentionally does NOT make the final pick —
the ordering *within* a tier is a judgment call (dependencies, what unblocks the most, what makes
a good foundation) that the model makes after reading the candidate issue bodies.

Slice ordering: work is preferred by slice number, lowest first (slice1 before slice2 before
slice3 …). Earlier slices are the foundation later ones build on, so finish them first. Within a
single slice, issues are bucketed by priority tier.

Usage:
    python todo_issues.py                       # all slices, ordered by slice number
    python todo_issues.py --slice slice2        # restrict to one slice
    python todo_issues.py --status "In Progress"

Priority tiers (highest first): bug > enhancement > future-enhancement > (other/untiered)
Output: JSON on stdout: {"status": ..., "total": ..., "slices": [ {slice, number, total, tiers}, ... ]}
`slices` is ordered by slice number ascending. Each candidate: {"number", "title", "labels"}.
"""
import argparse
import json
import re
import subprocess
import sys

PROJECT_NUMBER = "2"
PROJECT_OWNER = "rustycoopes"

# Highest priority first. An issue is placed in the first tier whose label it carries.
TIER_ORDER = ["bug", "enhancement", "future-enhancement"]

SLICE_RE = re.compile(r"^slice(\d+)$")


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


def slice_number(labels):
    """Return the lowest slice number among an issue's labels, or None if it carries no slice label."""
    nums = [int(m.group(1)) for label in labels if (m := SLICE_RE.match(label))]
    return min(nums) if nums else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default=None,
                    help="restrict to a single slice label (e.g. slice2); default: all slices")
    ap.add_argument("--status", default="Todo",
                    help="project Status value to filter by (default: Todo)")
    args = ap.parse_args()

    # slice number -> {tier: [candidates]}
    by_slice = {}
    for item in fetch_items():
        content = item.get("content") or {}
        number = content.get("number")
        if number is None:  # draft items with no linked issue
            continue
        if (item.get("status") or "") != args.status:
            continue
        labels = item.get("labels") or []
        snum = slice_number(labels)
        if snum is None:  # not part of any slice
            continue
        if args.slice is not None and args.slice not in labels:
            continue
        tiers = by_slice.setdefault(snum, {t: [] for t in TIER_ORDER + ["other"]})
        tiers[classify(labels)].append({
            "number": number,
            "title": content.get("title", ""),
            "labels": labels,
        })

    slices = []
    for snum in sorted(by_slice):  # slice number ascending — earliest slice first
        tiers = by_slice[snum]
        for t in tiers:
            tiers[t].sort(key=lambda c: c["number"])
        slices.append({
            "slice": f"slice{snum}",
            "number": snum,
            "total": sum(len(v) for v in tiers.values()),
            "tiers": tiers,
        })

    print(json.dumps({
        "status": args.status,
        "total": sum(s["total"] for s in slices),
        "slices": slices,
    }, indent=2))


if __name__ == "__main__":
    main()
