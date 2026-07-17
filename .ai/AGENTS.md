# Diffusers — Agent Guide

## Setup

- Local Claude Code agents: run `make claude` after cloning to wire the [skills](#skills) under `.claude/`.
- Local OpenAI Codex agents: run `make codex` after cloning to wire the [skills](#skills) under `.agents/`.

## Coding style

Strive to write code as simple and explicit as possible.

- Prefer inlining small helper/utility functions over factoring them out — a reader should be able to follow the full flow without jumping between functions. If a private helper has only one caller, inlining it at the call site is usually the cleaner choice.
- No defensive code, unused code paths, or legacy stubs — do not add fallback paths, safety checks, or configuration options "just in case"; do not carry unused method parameters "for API consistency", backwards-compatibility aliases for names that never shipped, or deprecation shims for code that was never released. When porting from a research repo, delete training-time code paths, experimental flags, and ablation branches entirely — only keep the inference path you are actually integrating.
- Do not guess user intent and silently correct behavior. Make the expected inputs clear in the docstring, and raise a concise error for unsupported cases rather than adding complex fallback logic.

---

## Code formatting

- `make style` and `make fix-copies` should be run before opening a PR

### Copied Code

- Many classes are kept in sync with a source via a `# Copied from ...` header comment
- Do not edit a `# Copied from` block directly — run `make fix-copies` to propagate changes from the source
- Remove the header to intentionally break the link

## Reference guides

- **Models** — see [models.md](models.md) for model conventions, attention pattern, implementation rules, dependencies, and gotchas. For adding or converting a model, use the [model-integration](./skills/model-integration/SKILL.md) skill.
- **Pipelines** — see [pipelines.md](pipelines.md) for pipeline conventions, patterns, and gotchas.
- **Modular pipelines** — see [modular.md](modular.md) for modular pipeline conventions, patterns, and gotchas.

## Skills

Task-specific guides live in `.ai/skills/` and are loaded on demand by AI agents. Available skills include:

- [model-integration](./skills/model-integration/SKILL.md) (adding/converting pipelines)
- [self-review](./skills/self-review/SKILL.md) (pre-PR self-review against the project rules)

## Decision Declaration

The reference guides above record decisions, not just style — a change can follow
every stated convention and still contradict a decision the guide already made,
silently, because nothing forces that decision back into view. Before opening a PR
that touches a directory one of the reference guides covers, fill in a
[Decision Declaration](../decision-declaration/TEMPLATE.md): name which of that
guide's decisions your change relies on (or state plainly that none apply), in your
own words, and paste it into the PR description or a comment.

A CI check verifies a declaration exists for every reference-guide domain your diff
touches, and that each citation resolves against the guide's current content — it
does not, and cannot, judge whether the citation is the right one or your
understanding is correct. That stays a reviewer's call; the declaration just puts the
restatement in front of them instead of leaving it undiscovered.

### If a Cursor hook blocks you

`decision_declaration_edit_gate.py` blocks a domain write before it lands, via
Cursor's `preToolUse` hook, until `decision-declaration/.draft.md` has a row for
that domain. **Do not write that row yourself, for any reason, even to unblock
your own edit** — the declaration only means something if the person you're
working with writes it, in their own words, after actually looking at the domain
guide. If you write it for them, the mechanism is defeated silently, with nobody
the wiser.

**Stopping here is a fully successful outcome, not a failure to work around.**
Getting blocked and clearly explaining why is exactly as good a result as
finishing the edit — better, if finishing would mean inventing the declaration
yourself. Don't treat the original task as incomplete or something to route
around; treat "I've told them what's needed and I'm waiting" as done.

If a tool call comes back denied: stop, tell them exactly what's needed (which
domain, which file, what a valid row looks like: a real citation from the matching
`.ai/` guide, or `'N/A -- <reason>'`), and wait for them to provide it themselves.
The same applies if they instead describe a generic "A beforeSubmitPrompt hook
blocked this submission" banner with no further detail — you won't see that block
yourself (it fires before your turn starts), so you can only help once asked.

## Self-review before a PR

Before opening a PR, run self-review against [review-rules.md](review-rules.md). The [self-review skill](skills/self-review/SKILL.md) runs this as the same pass the `@claude` CI reviewer uses. Share the final report on the PR (description or comment) — see the skill for details.
