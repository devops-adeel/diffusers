#!/usr/bin/env python3
"""Cursor `preToolUse` hook: Decision Declaration edit gate.

Unlike `beforeSubmitPrompt` (decision_declaration_gate.py), which can only block
the *next prompt* once a domain is already dirty, `preToolUse` fires *before* a
`Write` tool call executes -- confirmed empirically to actually block the edit in
the real Cursor GUI, see tech-screen/GAPS_AND_BLOCKERS.md SS7a. This hook uses that
to deny the edit itself, not just gate what comes after it.

Deliberately edit-scoped, not a port of beforeSubmitPrompt's "any domain touched
anywhere in the diff" check: it only asks whether *this specific file* belongs to
an undeclared domain. Applied at once-per-tool-call granularity, the coarser
"anything dirty blocks everything" rule would deny most Write calls anywhere in the
repo the moment any domain goes dirty -- a much harsher failure mode to hit live
than beforeSubmitPrompt's once-per-turn version of the same tradeoff. This is a
deliberate behavior change, not a like-for-like port -- see GAPS_AND_BLOCKERS.md.

Known, disclosed coverage gaps (not fixed here -- see the plan this shipped from):
- `Delete` is a separate tool_name in Cursor's own schema; this hook's matcher
  (`"Write"`) never sees deletions of domain files. Caught by beforeSubmitPrompt on
  the next turn instead (a deleted tracked file shows up in `git status
  --porcelain`), not blocked at the moment of deletion.
- A domain file edited via a shell command (sed, a heredoc, etc.) bypasses this
  hook's matcher entirely for the same reason -- also caught by beforeSubmitPrompt
  as a backstop, by design (this hook does not widen its matcher to compensate;
  see GAPS_AND_BLOCKERS.md for why that would ship unverified surface).
Both hooks are kept running together on purpose -- see GAPS_AND_BLOCKERS.md.

Same lightweight declaration bar as beforeSubmitPrompt (any non-empty row per
domain counts, no citation-strength check -- that stays at self-review time and at
CI) and the same fail-open philosophy, both imported from / matching
check_decision_linkage.py so the two hooks and the CI check can't silently drift
apart from each other.
"""
import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "decision-declaration")
)
from check_decision_linkage import (  # noqa: E402
    DRAFT_FILE,
    compute_touched_domains,
    declared_domains_from_draft,
)


def to_relative_path(absolute_path, workspace_roots):
    """Cursor sends an ABSOLUTE path in tool_input.file_path for the Write tool --
    confirmed empirically against real GUI payloads, not assumed from docs (see
    GAPS_AND_BLOCKERS.md SS7a, where getting this wrong produced a false negative
    that looked exactly like "Cursor ignores deny"). DOMAIN_PATH_PREFIXES is
    relative-to-repo-root, so this has to be undone before matching."""
    path = str(absolute_path)
    for root in workspace_roots or []:
        root = str(root).rstrip("/")
        if path.startswith(root + "/"):
            return path[len(root) + 1:]
    return path  # no matching root -- fall through, won't match any domain prefix


def allow(message=None):
    out = {"permission": "allow"}
    if message:
        out["agentMessage"] = message
    print(json.dumps(out))


def deny(domain, absolute_path):
    msg = (
        f"Decision Declaration missing for: {domain}. This edit to {absolute_path} "
        f"is blocked until a row exists in {DRAFT_FILE} for it (a real citation "
        f"from the matching .ai/ guide, or 'N/A -- <reason>')."
    )
    # Both casings emitted deliberately -- the exact combination empirically proven
    # to work in the real Cursor GUI (GAPS_AND_BLOCKERS.md SS7a), not a guess at
    # which one Cursor reads.
    print(json.dumps({
        "permission": "deny",
        "userMessage": msg,
        "agentMessage": msg,
        "user_message": msg,
        "agent_message": msg,
    }))


def main():
    try:
        payload = json.load(sys.stdin)

        if payload.get("tool_name") != "Write":
            # The hooks.json matcher already filters to "Write" -- this is a
            # defensive check, not a matcher substitute; don't assume the matcher
            # is the only thing standing between this script and an unexpected
            # payload shape.
            allow()
            return

        tool_input = payload.get("tool_input") or {}
        absolute_path = tool_input.get("file_path")
        if not absolute_path:
            allow()
            return

        workspace_roots = payload.get("workspace_roots") or []
        repo_dir = workspace_roots[0] if workspace_roots else os.getcwd()

        relative_path = to_relative_path(absolute_path, workspace_roots)
        touched = compute_touched_domains([relative_path])
        if not touched:
            allow()  # this edit isn't under any tracked domain
            return

        missing = touched - declared_domains_from_draft(repo_dir)
        if missing:
            deny(", ".join(sorted(missing)), absolute_path)
        else:
            allow()
    except Exception as exc:  # noqa: BLE001 -- deliberate: fail open, not silent
        allow(message=f"decision-declaration-edit-gate error, allowing through: {exc!r}")


if __name__ == "__main__":
    main()
