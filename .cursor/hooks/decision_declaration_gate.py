#!/usr/bin/env python3
"""Cursor `beforeSubmitPrompt` hook: Decision Declaration draft gate.

Cursor cannot block a native file edit before it happens (no `beforeFileEdit`
event exists; `afterFileEdit` is observation-only) -- confirmed against two
independent sources, see tech-screen/GAPS_AND_BLOCKERS.md. `beforeSubmitPrompt` is
the earliest point Cursor can genuinely deny anything relevant, so the gate fires
here instead: once a domain has changes with no declaration row, the *next* prompt
is denied until one exists, in TEMPLATE.md's format, pointed at DRAFT_FILE.

Deliberately a lighter bar than the CI check: any non-empty row per touched domain
passes here, even a tentative or wrong guess -- matching model-integration's own
"draft, not commitment" framing. Full citation-strength verification (does the
quoted text actually resolve against .ai/<domain>.md) stays at self-review time and
at CI; duplicating that strength here would block someone from starting work on a
case they can't yet articulate precisely.

Fails open on purpose: any unexpected error here falls back to allowing the prompt
through with a diagnostic userMessage, rather than an uncaught crash freezing the
session (Cursor's own hook-failure default is fail-open too, this just makes it
explicit and demo-legible instead of an opaque stack trace). See
GAPS_AND_BLOCKERS.md for why fail-open was chosen over failClosed for the live demo.

Domain map and row-parsing logic are imported from check_decision_linkage.py, not
duplicated -- so this hook and the CI check can never silently drift apart.
"""
import json
import os
import subprocess
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "decision-declaration")
)
from check_decision_linkage import (  # noqa: E402
    DRAFT_FILE,
    compute_touched_domains,
    declared_domains_from_draft,
)


def branch_reference(repo_dir):
    """The ref this branch actually diverged from -- its own upstream tracking
    branch, NOT a hardcoded 'origin/main'. A hardcoded main is wrong the moment a
    branch is deliberately layered on top of another already-merged branch (as on
    this very demo fork): diffing against main would then pick up all of that
    prior, already-reviewed history as if it were newly touched right now."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=repo_dir, capture_output=True, text=True, timeout=5,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None  # no upstream (e.g. a brand new local branch) -- nothing "since branch point" to diff yet


def changed_paths(repo_dir):
    """Everything that would appear in the eventual PR diff right now: committed
    since this branch's own reference point, unioned with uncommitted changes --
    not raw `git status` alone, which would also catch unrelated stale local state
    left over from earlier, unrelated work."""
    paths = set()
    ref = branch_reference(repo_dir)
    try:
        if ref is None:
            raise subprocess.CalledProcessError(1, "no-upstream")
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=repo_dir, capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "--name-only", merge_base, "HEAD"],
            cwd=repo_dir, capture_output=True, text=True, check=True, timeout=5,
        ).stdout
        paths.update(line.strip() for line in diff.splitlines() if line.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass  # no merge-base available -- fall through to working-tree status only

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir, capture_output=True, text=True, timeout=5,
    ).stdout
    for line in status.splitlines():
        p = line[3:].split(" -> ")[-1].strip()  # porcelain: "XY path" or "XY old -> new"
        if p:
            paths.add(p)
    return paths


def allow(message=None):
    out = {"continue": True, "permission": "allow"}
    if message:
        out["agentMessage"] = message
    print(json.dumps(out))


def deny(missing):
    msg = (
        f"Decision Declaration missing for: {', '.join(sorted(missing))}. "
        f"Add a row to {DRAFT_FILE} for each (a real citation from the matching "
        f".ai/ guide, or 'N/A -- <reason>') before continuing."
    )
    # Cursor's beforeSubmitPrompt schema is {"continue": bool, "user_message": str}
    # -- no "permission" or "agent_message" field exists for this hook event (it
    # fires before the model is invoked, so there's no agent turn to relay a
    # message through anyway). The prior version sent "userMessage"/"agentMessage"/
    # "permission", none of which this event reads, which is why `continue: false`
    # correctly blocked the prompt while the custom text never rendered -- Cursor
    # fell back to its own generic banner. Both casings kept on user_message as a
    # hedge, matching decision_declaration_edit_gate.py's approach.
    print(json.dumps({
        "continue": False,
        "user_message": msg,
        "userMessage": msg,
    }))


def main():
    try:
        payload = json.load(sys.stdin)
        repo_dir = (payload.get("workspace_roots") or [os.getcwd()])[0]

        touched = compute_touched_domains(changed_paths(repo_dir))
        missing = touched - declared_domains_from_draft(repo_dir)

        if missing:
            deny(missing)
        else:
            allow()
    except Exception as exc:  # noqa: BLE001 -- deliberate: fail open, not silent
        allow(message=f"decision-declaration-gate error, allowing through: {exc!r}")


if __name__ == "__main__":
    main()
