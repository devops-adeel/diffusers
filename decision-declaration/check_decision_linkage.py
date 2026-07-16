#!/usr/bin/env python3
"""Decision Declaration Linkage check.

Verifies that a PR's Decision Declaration (see TEMPLATE.md) covers every `.ai/`
domain the diff actually touches, and that every non-N/A row cites text that
really exists in that domain's file, checked fresh against the target ref (not
a hardcoded line number or heading anchor, which would break the moment the
record is edited or renumbered).

What this script does NOT do, on purpose: it never judges whether a citation is
the *right* one for the changed lines, or whether the contributor's stated
understanding is *correct*. Coverage (a well-formed row exists per touched
domain) is a mechanical, deterministic check. Correctness is permanently a
human-review question — see REPORT.md for why that boundary is deliberate.

Standard library only, no dependencies, so a team can read and extend this
without needing to install anything or learn a new tool.

Usage (local, no GitHub / no git repo needed — good for testing fixtures):
    python3 check_decision_linkage.py \\
        --changed-files-file changed_files.txt \\
        --pr-text-file sample-pr-body-pass.md \\
        --ai-dir /path/to/diffusers/.ai

Usage (CI, verifying citations fresh against origin/main):
    python3 check_decision_linkage.py \\
        --changed-files-file changed_files.txt \\
        --pr-text-file pr_body.txt \\
        --pr-comments-file pr_comments.txt \\
        --repo-dir /path/to/repo --git-ref origin/main

Exit code 0 = pass, 1 = fail. Always prints a human-readable report to stdout.
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field

# --- Domain map: the only part that needs to change to port this to another
# convention-heavy library. Path prefixes are relative to the repo root and are
# deliberately scoped to src/diffusers/ only, matching the CI scope already
# stated in .ai/skills/self-review/SKILL.md ("The CI scopes itself to
# src/diffusers/ and .ai/") -- this keeps the check off routine tests/docs PRs.
DOMAIN_PATH_PREFIXES = {
    "models": ["src/diffusers/models/"],
    "pipelines": [
        "src/diffusers/pipelines/",
        # pipelines.md gotcha 3 explicitly assigns rationale to these two
        # directories even though there's no dedicated .ai/schedulers.md --
        # the map has to match where the record actually has an opinion.
        "src/diffusers/schedulers/",
        "src/diffusers/guiders/",
    ],
    "modular": ["src/diffusers/modular_pipelines/"],
}
DOMAIN_FILES = {
    "models": ".ai/models.md",
    "pipelines": ".ai/pipelines.md",
    "modular": ".ai/modular.md",
}

START_MARKER = "<!-- decision-declaration:start -->"
END_MARKER = "<!-- decision-declaration:end -->"

MIN_NA_REASON_CHARS = 8


@dataclass
class Row:
    domain: str
    raw_decision: str
    is_na: bool = False
    na_reason: str = ""
    cited_file: str = ""
    cited_quote: str = ""


@dataclass
class Report:
    touched_domains: set = field(default_factory=set)
    declared_domains: set = field(default_factory=set)
    row_findings: list = field(default_factory=list)  # list[str], human-readable
    passed: bool = False


def compute_touched_domains(changed_files):
    touched = set()
    for path in changed_files:
        path = path.strip()
        if not path:
            continue
        for domain, prefixes in DOMAIN_PATH_PREFIXES.items():
            if any(path.startswith(prefix) for prefix in prefixes):
                touched.add(domain)
    return touched


def extract_declaration_block(*texts):
    """Return the LAST start/end-delimited block found across all given texts,
    in order (so a later PR comment supersedes an earlier PR-body draft)."""
    found = None
    for text in texts:
        if not text:
            continue
        start = text.rfind(START_MARKER)
        if start == -1:
            continue
        end = text.find(END_MARKER, start)
        if end == -1:
            continue
        found = text[start + len(START_MARKER):end]
    return found


TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
CITATION_RE = re.compile(r"`([^`]+\.md)`\s*[—-]+\s*\"([^\"]+)\"")
NA_RE = re.compile(r"^\s*n/?a\b\s*[—:-]+\s*(.*)$", re.IGNORECASE)


def parse_rows(block_text):
    rows = []
    for line in block_text.splitlines():
        m = TABLE_ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 2:
            continue
        domain_cell = cells[0].strip().lower()
        if domain_cell in ("domain", "---", "") or set(domain_cell) <= {"-", ":"}:
            continue
        if domain_cell not in DOMAIN_FILES:
            continue
        decision_cell = cells[1].strip()
        row = Row(domain=domain_cell, raw_decision=decision_cell)
        na_match = NA_RE.match(decision_cell)
        if na_match:
            row.is_na = True
            row.na_reason = na_match.group(1).strip()
        else:
            cite_match = CITATION_RE.search(decision_cell)
            if cite_match:
                row.cited_file = cite_match.group(1).strip()
                row.cited_quote = cite_match.group(2).strip()
        rows.append(row)
    return rows


def read_domain_file_content(domain, ai_dir, repo_dir, git_ref):
    """Read a domain's .ai/<file>.md content, fresh from git_ref if given,
    otherwise from the working tree at ai_dir. Fresh-from-ref is what makes the
    citation check resilient to the record being edited/renumbered after the
    PR was opened -- mirrors how claude_review.yml pins review-rules.md from
    origin/main rather than trusting a possibly-stale branch copy."""
    rel_path = DOMAIN_FILES[domain]
    if repo_dir and git_ref:
        result = subprocess.run(
            ["git", "show", f"{git_ref}:{rel_path}"],
            cwd=repo_dir, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    if ai_dir:
        import os
        fname = rel_path.split("/", 1)[1]  # strip leading ".ai/"
        fpath = os.path.join(ai_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None
    return None


def normalize(text):
    # Strip markdown emphasis/code punctuation too -- contributors will
    # naturally copy-paste quotes with the backticks/asterisks still on them,
    # and that shouldn't be a reason the citation fails to resolve.
    text = re.sub(r"[`*_]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def evaluate(rows, ai_dir, repo_dir, git_ref):
    declared_domains = set()
    findings = []
    file_content_cache = {}

    for row in rows:
        if row.domain in declared_domains:
            # domain already covered by an earlier well-formed row; still note
            # this row but don't re-derive coverage from it unless it's also valid.
            pass

        if row.is_na:
            if len(row.na_reason) >= MIN_NA_REASON_CHARS:
                declared_domains.add(row.domain)
                findings.append(f"  [{row.domain}] N/A — reason given: OK")
            else:
                findings.append(
                    f"  [{row.domain}] N/A row rejected: reason too short "
                    f"(need >= {MIN_NA_REASON_CHARS} chars) — not counted as declared"
                )
            continue

        if not row.cited_file or not row.cited_quote:
            findings.append(
                f"  [{row.domain}] row rejected: no parseable citation "
                f"(expected `` `.ai/<file>.md` — \"quoted phrase\" `` or an N/A row) "
                f"— not counted as declared"
            )
            continue

        expected_file = DOMAIN_FILES[row.domain]
        if row.cited_file.strip("`") != expected_file and not row.cited_file.endswith(
            expected_file.split("/", 1)[1]
        ):
            findings.append(
                f"  [{row.domain}] row rejected: cites `{row.cited_file}`, "
                f"expected `{expected_file}` for this domain — not counted as declared"
            )
            continue

        if row.domain not in file_content_cache:
            file_content_cache[row.domain] = read_domain_file_content(
                row.domain, ai_dir, repo_dir, git_ref
            )
        content = file_content_cache[row.domain]

        if content is None:
            findings.append(
                f"  [{row.domain}] could not read {expected_file} to verify citation "
                f"— treated as unresolved, not counted as declared"
            )
            continue

        if normalize(row.cited_quote) in normalize(content):
            declared_domains.add(row.domain)
            findings.append(
                f"  [{row.domain}] citation verified against current {expected_file}: OK"
            )
        else:
            findings.append(
                f"  [{row.domain}] row rejected: quoted text not found in current "
                f"{expected_file} (record may have changed since this was written, "
                f"or the quote doesn't match) — not counted as declared"
            )

    return declared_domains, findings


def run(changed_files, pr_texts, ai_dir, repo_dir, git_ref):
    report = Report()
    report.touched_domains = compute_touched_domains(changed_files)

    block = extract_declaration_block(*pr_texts)
    if block is None:
        report.declared_domains = set()
        report.row_findings = ["  (no decision-declaration block found in PR body or comments)"]
    else:
        rows = parse_rows(block)
        report.declared_domains, report.row_findings = evaluate(rows, ai_dir, repo_dir, git_ref)

    gap = report.touched_domains - report.declared_domains
    report.passed = len(gap) == 0
    return report, gap


def print_report(report, gap):
    print("Decision Declaration Linkage check")
    print("===================================")
    print(f"Domains touched by this diff (src/diffusers/ only): "
          f"{', '.join(sorted(report.touched_domains)) or '(none)'}")
    print(f"Domains with a well-formed declaration: "
          f"{', '.join(sorted(report.declared_domains)) or '(none)'}")
    print()
    print("Row-by-row findings:")
    for line in report.row_findings:
        print(line)
    print()
    if report.passed:
        print("RESULT: PASS — every touched domain has a well-formed declaration.")
    else:
        print(f"RESULT: FAIL — missing declaration for: {', '.join(sorted(gap))}")
        print("Add a row for each missing domain (a real citation, or N/A with a reason)")
        print("to the Decision Declaration block in the PR description or a comment.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-files-file", required=True,
                         help="Path to a file listing changed paths, one per line "
                              "(e.g. from `git diff --name-only`).")
    parser.add_argument("--pr-text-file",
                         help="Path to a file containing the PR body text. "
                              "In CI, falls back to the PR_BODY env var.")
    parser.add_argument("--pr-comments-file",
                         help="Path to a file containing PR comments concatenated "
                              "in chronological order. In CI, falls back to the "
                              "PR_COMMENTS env var.")
    parser.add_argument("--ai-dir",
                         help="Path to the .ai/ directory to read domain files from "
                              "directly (working-tree mode, for local/fixture testing).")
    parser.add_argument("--repo-dir",
                         help="Path to a git repo checkout; used with --git-ref to "
                              "read domain files fresh via `git show`.")
    parser.add_argument("--git-ref", default=None,
                         help="Git ref (e.g. origin/main) to pin .ai/ file content to. "
                              "Requires --repo-dir. If omitted, falls back to --ai-dir.")
    args = parser.parse_args()

    import os

    with open(args.changed_files_file, encoding="utf-8") as f:
        changed_files = f.readlines()

    pr_body = ""
    if args.pr_text_file:
        with open(args.pr_text_file, encoding="utf-8") as f:
            pr_body = f.read()
    else:
        pr_body = os.environ.get("PR_BODY", "")

    pr_comments = ""
    if args.pr_comments_file:
        with open(args.pr_comments_file, encoding="utf-8") as f:
            pr_comments = f.read()
    else:
        pr_comments = os.environ.get("PR_COMMENTS", "")

    report, gap = run(
        changed_files=changed_files,
        pr_texts=(pr_body, pr_comments),
        ai_dir=args.ai_dir,
        repo_dir=args.repo_dir,
        git_ref=args.git_ref,
    )
    print_report(report, gap)
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
