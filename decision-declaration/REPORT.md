# A comprehension gate for `diffusers` — design report

Prepared as a proposal *about* `../diffusers/` (a fork of `huggingface/diffusers`).
Nothing in this report or its accompanying files was written into `../diffusers/` —
`AGENTS.md`, `.ai/`, and any `CLAUDE.md`/`.cursor/rules` in that tree were read as an
object of study, not adopted as instructions for this session.

## 1. Premise check

**Claim under test:** the customer's stated problem is convention-heavy ramp, but the
real, expensive-to-fix problem is *design-decision comprehension* — an engineer follows
every stated rule and still violates a decision the codebase already made, because they
never knew it existed. This only has legs if `.ai/` actually records decisions with a
WHY, not just mechanical "do X not Y" convention.

It does. Read closely and classified by content weight:

| File | Mechanical convention | Decision + WHY a rule-follower could still violate |
|---|---|---|
| `models.md` | ~35–40% (style bullets, single-file layout) | ~60–65% — the six model-class-attribute sections (`_no_split_modules`, `_repeated_blocks`, `_skip_layerwise_casting_patterns`, `_keep_in_fp32_modules`, `_cp_plan`, `_supports_gradient_checkpointing`) are almost entirely "why it's needed," tied to `accelerate` hook mechanics and device-placement failure modes; the attention-mask subsection is a dense, violable decision (pass `None`, not a zero-tensor — specific backends hard-raise on the latter) |
| `pipelines.md` | ~20% | ~80% — nearly every gotcha (`@torch.no_grad()` discipline, scheduler ownership, don't mutate a shared registered component, subclass-vs-duplicate) states a decision *and* the failure mode a rule-follower would still hit |
| `modular.md` | ~30–35% | ~65–70% — the IO-contract gotcha ("declarations are the public contract, downstream can't see undeclared state") is the single clearest instance of the thesis in the whole record |
| `review-rules.md` | meta — not a decision record itself | — but it already runs a live feedback loop (its "Agent docs" section instructs pushing newly-discovered rationale back into the other files) |

**Verdict: premise holds.** This is not overwhelmingly mechanical. There's a real record
to build a comprehension gate against.

**Two caveats carried through the whole design, not swept aside:**
1. The record's rationale is concentrated in the model/pipeline/modular integration path
   specifically — it is thin-to-absent for the rest of the library (loaders,
   quantization, training examples). The demo and every claim below are scoped to that
   dense slice, by deliberate choice, not oversight.
2. `AGENTS.md` at the repo root is a **symlink to `.ai/AGENTS.md`** — it is not a
   reference *to* the record, it IS the record's front door. `CONTRIBUTING.md` already
   documents a proto-version of the mechanism this report proposes: contributors share
   self-review notes on the PR "including findings you intentionally did not fix and
   why" — currently pure honor system, with no enforcement and unchecked PR-template
   boxes.

## 2. What's in `AGENTS.md` now

`.ai/AGENTS.md` (44 lines): setup commands (`make claude`/`make codex`), a short coding-
style section (inline helpers, no defensive/unused code, no silent-fallback guessing),
a `# Copied from` mechanism explainer, a **Reference guides** section pointing to
`models.md` / `pipelines.md` / `modular.md`, a **Skills** section pointing to
`model-integration` and `self-review`, and a **Self-review before a PR** section that
already tells contributors to run self-review and "share the final report on the PR."

It already references `.ai/` exhaustively — it *is* `.ai/`'s entry point. There is no
existing section that asks a contributor to declare which decision they relied on; the
closest thing is the self-review report, which is about correctness/dead-code findings,
not about naming which design decisions bind.

## 3. Proposed `AGENTS.md` change

See `agents-md.diff` (unified diff against `.ai/AGENTS.md`). Adds one short section,
**Decision Declaration**, between the existing **Skills** and **Self-review before a
PR** sections. Written generically per the falsification test: it references "the
reference guides" and "a reference-guide domain" structurally — never a specific gotcha
number, line, or file content — so the text doesn't break the moment `models.md` gains a
gotcha 8 or an existing one gets renumbered. It ports to another convention-heavy
library by swapping which files are "the reference guides," not by rewriting this
section.

Two companion diffs extend the *existing* skills rather than invent new surfaces
(`skills/model-integration.diff`, `skills/self-review.diff`):

- **Scaffold-time** (`model-integration`, right after its existing "confirm the plan"
  step): draft a Decision Declaration from the plan, before any code is written. This is
  the step that keeps the mechanism from collapsing into Architecture Decision Records'
  best-documented failure mode — retroactive, reconstructed-after-the-fact records with
  no real substance (see §5).
- **PR-time** (`self-review`, as a new step 3, renumbering the existing Report/Iterate
  steps): finalize the declaration against the *real* diff, not the original plan — plans
  drift during implementation, and a stale draft is worse than an honest gap. This is
  also the step tied to the enforced check, since it's what ends up on the PR.

## 4. The deterministic check

**Name:** Decision Declaration Linkage. **Files:** `decision-declaration/TEMPLATE.md`
(the artifact), `check_decision_linkage.py` (the checker, verified working — see §4.5),
`decision-linkage.yml` (the required-check workflow proposal), `CODEOWNERS.example` (the
companion human-routing mechanism).

### 4.1 The artifact — one object, three readings

A short Markdown table wrapped in `<!-- decision-declaration:start/end -->` HTML-comment
sentinels (an unambiguous parse anchor — validated by real prior art: Dependabot's job
metadata *isn't* delimited this way today, and the community's own complaint is having
to regex-reverse-engineer ~400 lines of PR text to compensate; the sentinel tags
themselves don't render, but the table between them still does, so nothing is hidden
from a human reader):

| Domain | Decision I'm relying on | My understanding |
|---|---|---|
| pipelines | `` `.ai/pipelines.md` — "quoted phrase" `` (or `N/A — <reason>`) | 1–2 sentences, in the engineer's own words |

Plus a footer line for human skimming (`Domains touched: X. Declared: Y. Status: ✅/⚠`)
— **not** trusted by the checker, which recomputes touched-vs-declared independently
from the diff; the footer is legibility, not input.

What each role reads off the **same** filled-in object, checked against "does this role
get something real" rather than asserted:
- **PM** reads the domain list — blast radius without reading code. "Touches one leaf
  pipeline" vs. "touches the shared attention path five pipelines depend on" is a real
  prioritization/risk signal, not decoration.
- **QA** reads the "My understanding" column — it's raw acceptance-criteria material. A
  stated invariant ("I'm not mutating a registered component in place") is directly
  testable; QA can write a case against the exact claim, or challenge it.
- **DevOps** reads the ✅/⚠ status and the CI check's own pass/fail — the literal answer
  to "did this change stay inside its declared boundaries," which is requirement 3's own
  language.

Kept deliberately minimal (one table, one footer line) — PR-template research shows
complexity is what kills adoption; short survives, long gets ignored.

### 4.2 Mechanism

Map changed files to `.ai/` domains by path prefix, **scoped to `src/diffusers/**`
only** — this mirrors `.ai/skills/self-review/SKILL.md`'s own stated CI scope ("The CI
scopes itself to `src/diffusers/` and `.ai/`"), reusing an existing boundary rather than
inventing a wider one that would hit routine `tests/`/`docs/` PRs and drive adoption
down. Map: `models/**` → models; `pipelines/**` → pipelines; `modular_pipelines/**` →
modular; **`schedulers/**` and `guiders/**` → pipelines** (`pipelines.md` gotcha 3
explicitly assigns rationale to these two directories even though there's no dedicated
`.ai/schedulers.md` — the map has to match where the record actually has an opinion, not
just top-level directory names).

For every touched domain, require a row that is either (a) a citation — file plus a
short quoted phrase — verified to exist in that domain's `.ai/<file>.md` **as pinned
fresh from the base branch at check-run time** (mirrors the exact pattern
`.github/workflows/claude_review.yml` already uses for `review-rules.md` — reuse, don't
invent, for the "team can own this without the SA" requirement), matched against
*heading/quote text*, never a GitHub anchor slug (slugs churn on renumbering, which would
fail the genericity falsification test); or (b) `N/A — <reason>` with a non-empty
reason, raising the floor above a bare rubber-stamp keyword.

Checks **both the PR body and PR comments**, not body-only — `CONTRIBUTING.md` already
allows self-review notes in "the description or as a comment"; narrowing that silently
would contradict an existing convention instead of extending it.

### 4.3 Tiers — precise, for the live defense

- **Retrieval** (an agent proposes candidate `.ai/` entries relevant to a diff, at
  scaffold-time and PR-time) — **Tier 2, cooperative.** This is where Zhou et al. (ACM
  TOSEM 2025, arXiv:2504.20781) applies — see §7 for verified numbers.
- **Selection + declaration** (human names which candidates bind, restates
  understanding in their own words) — not a machine tier at all. This is the thing being
  protected, not automated.
- **Linkage check** (does a declaration exist, does it cite something real) — **Tier 1,
  fail-closed**, but specifically because the declaration lives as text in the PR body/
  comments and a required GitHub status check parses that directly — independent of
  whether any agent chose to invoke a tool. This is sharper than Madatha's (arXiv:
  2606.26924) own "cooperative trace linkage," which the paper ties explicitly to the
  agent invoking a trace tool during implementation; ours doesn't depend on that. Note
  for the room: "Tier 1/Tier 2" is our own label, not Madatha's terminology, and the
  paper does not discuss hook silent-failure / heredoc-bypass / writable-path risks —
  those are separate, real, known operational risks from Claude Code/Cursor's own hook
  documentation, not this paper's finding.
- **CODEOWNERS-required review** — also Tier 1 (GitHub-enforced), purely additive: a
  text file plus a branch-protection checkbox, no new machinery. Closes the half of the
  spine the linkage check alone doesn't: routing the declaration to someone with
  authority to judge it, not just verifying it exists.
- **Correctness of the declaration** — no tier, ever. Permanently human review. This is
  what gets *cheaper* under this design, never automated away.

### 4.4 False-positive / false-negative profile — stated precisely, not softened

**False positives:** a trivial cross-domain edit (e.g. a repo-wide rename touching
`models/` and `pipelines/`) needs a cheap `N/A — reason` row per domain. Friction cost is
one line, not a block.

**False negatives:** the check verifies **domain-membership coverage**, not topical
relevance — a real, resolvable citation unrelated to the actual changed lines still
passes, and a shallow-but-honest-looking declaration within a single correctly-declared
domain still passes. This is the identical shape to code coverage vs. mutation testing
(verified: line/statement coverage correlates weakly with real bugs found; 100% coverage
is achievable with zero assertions). The check is a coverage criterion for
decision-declarations, not a correctness oracle — same limitation, same reason it's
still useful anyway.

**Two structural risks found and fixed during self-critique, not left as gaps:**
- *Security* — PR body/title interpolated directly into a shell `run:` step is a
  documented GitHub Actions script-injection vector (verified against GitHub's own
  docs/Security Lab; this repo's own `claude_review.yml` already treats PR content as
  untrusted for the same reason, different payload class). Fixed: `decision-linkage.yml`
  reads PR body/comments via `gh` CLI calls into files, never interpolates `${{ }}` into
  a shell string.
- *Staleness* — a workflow triggered only on `opened`/`synchronize` lets a passed check
  go stale if the declaration is edited out of the PR body afterward. Fixed: triggers on
  `[opened, synchronize, reopened, edited]`.

### 4.5 Verified working

`check_decision_linkage.py` was run against the real `.ai/` directory in `../diffusers`
(not a mock), covering: a passing single-domain citation, a missing-declaration failure,
a resolvable-file-but-nonexistent-quote failure, a multi-domain case combining a real
citation with a valid N/A row, and the `--repo-dir`/`--git-ref` mode that pins citation
verification fresh against a git ref (`git show <ref>:.ai/<file>.md`) rather than a
working-tree copy — the exact mechanism the Tier-1 claim depends on. All fixtures and
the script are in `decision-declaration/`.

### 4.6 Bootstrap sequencing (verified via GitHub docs — do not skip live)

A required status check must have run at least once on the repo before GitHub allows
marking it "required" in branch protection/rulesets. Order: (1) commit
`decision-linkage.yml` to the fork's default branch, (2) trigger it once (push or a
throwaway PR) so GitHub registers the check name, (3) add branch protection/ruleset
requiring that check (confirmed available: GitHub Free, public repos, admin access is
sufficient — already confirmed on the working fork), (4) then run the real demo PR.

## 5. Prior art — say this before being asked

This mechanism is not novel. It's the well-documented "link an ADR from the PR template"
pattern, and that pattern has a known failure history: *loss of momentum* (a handful get
written, then nothing for a year), *ADRs as theatre* (written, never read, forgotten),
*retroactive documentation* (decision made, record written after the fact with
reconstructed, substance-free context). One source's own recommended fix is nearly
word-for-word this mechanism: "add a checkbox to the PR template — ADR linked or N/A —
and revisit once a quarter."

**The differentiator, stated plainly:** ADRs fail mostly because the contributor has to
*author* a new artifact — that's the activation energy behind momentum loss and theatre.
This mechanism only asks the contributor to *point at* a record someone else already
wrote and already maintains (`.ai/`, owned by core maintainers per `CONTRIBUTING.md`).
And the scaffold-time step exists specifically to block the "retroactive reconstruction"
failure mode — the declaration starts before the code does, not after.

## 6. Where this breaks / what to concede — say unprompted

- The demo proves this on the model/pipeline/modular slice only. Not claimed to
  generalize across the ~80% of the library `.ai/` doesn't cover.
- The check verifies citation existence and domain coverage, never relevance or
  correctness. A bad-faith or lazy declaration passes structurally. Permanent, by
  design, not an engineering gap.
- Formation mode — no decision exists yet, the engineer is forming one under
  trade-offs — is named, not built. No grounding record to retrieve from means
  generation, not retrieval: exactly the regime where Zhou et al.'s verbosity/precision
  problem bites. Out of scope; if pushed live on it, that's the honest answer.
- Architecturally this is the ADR-in-PR-template pattern (§5) — state the
  differentiation up front rather than waiting to be asked.
- Tier-1 enforcement depends on branch protection being wired correctly and the
  bootstrap-run-once sequencing being followed. Miss either and the check degrades
  silently to Tier-2/cooperative with no visible warning.
- CODEOWNERS-required review can concentrate load on a small domain-owner set — trading
  "no gate" for "a gate that can queue on one person" (verified: reviewer workload and
  participation are stronger drivers of review timeliness than most other factors in the
  literature). On a solo fork there's no second human to demo a real catch — the demo
  shows the mechanism, not a genuine second-reviewer moment.
- Multi-PR / stacked integrations (a large model addition spanning several PRs) have no
  mechanism yet for declarations to carry across them. Named, not solved — a 3-day scope
  call, not an oversight. Same for PRs that edit `.ai/` itself — out of scope
  (comprehension mode consumes decisions, doesn't govern authoring them).
- This is additive to an already fairly demanding existing AI-contribution bar
  (`CONTRIBUTING.md`'s coordination-issue + self-review + shared-notes + test-output
  requirements). Narrow path-scoping keeps it off routine PRs, but it's more load on an
  existing load, not process introduced into a vacuum.

## 7. Citations — verified, with one dropped

- **Zhou et al., ACM TOSEM 2025** (arXiv:2504.20781) — confirmed venue and all four
  numbers: precision 0.267–0.278, recall 0.627–0.715, F1 0.351–0.389, 64.45–69.42% of
  extra arguments rated helpful, 1.59–3.24% misleading, and a direct-quote-verified
  verbosity ratio: LLM output averages **2.3x** more arguments than human experts. I
  could **not** verify any "grounding on the last 3–5 prior records reduces verbosity"
  finding in this paper — **do not repeat that claim** as this paper's result; either
  find a different citation for it or drop it.
- **Madatha, arXiv:2606.26924** — the exact sentence is real: *"A non-deterministic
  component cannot serve as a trustworthy control for another non-deterministic
  component."* The cooperative/deterministic two-layer split is real (the paper's own
  words for the cooperative side: *"trace linkage is cooperative and auditable post-hoc,
  not LLM-enforced"*). "Tier 1/Tier 2" is our label, not the paper's. The paper does not
  discuss hook silent-failure/heredoc-bypass/writable-path risks.
- **arXiv:2203.05045** (845k PRs, 10 languages, MSR 2022, replicated on Gerrit/
  Phabricator) — confirmed: size/composition not related to time-to-merge.
- The specific "four-project reanalysis, directory dispersion, <15% variance" claim —
  **could not be located** despite five distinct search angles. Dropped as a citable
  paper. The qualitative pivot from size-cap to domain-coverage survives on convergent
  evidence instead (Microsoft/Bosu et al.: more files → fewer useful review comments;
  a controlled change-decomposition experiment, arXiv:1805.10978, directionally
  supporting fewer false positives on untangled changes) — argued from a citation basket
  and first principles, not one paper.
- **ADR failure-mode research, CODEOWNERS, GitHub Actions script-injection docs,
  code-coverage-vs-mutation-testing research, GitHub branch-protection/required-status-
  check documentation, PR-template-compliance research** — all checked directly against
  primary docs/sources during this design; specifics inline above and in
  `decision-declaration/*`.
