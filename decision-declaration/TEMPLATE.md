<!--
DECISION DECLARATION — fill this in and paste it into the PR description (or a PR
comment). The block between the start/end markers below is what the "Decision
Declaration Linkage" check parses — everything outside the markers is ignored, so feel
free to write normal PR-description prose around it.

How to fill in a row:
  - Domain: one of the domains this PR's diff touches under src/diffusers/ — models,
    pipelines, or modular. (schedulers/ and guiders/ count as "pipelines" — pipelines.md
    already treats them as pipeline-owned rationale.) The checker computes which domains
    your diff actually touches independently from git — it does not trust this table to
    self-report that, only to *cover* it.
  - Decision I'm relying on: either
      (a) a real citation — the domain file plus a short phrase quoted directly from it,
          e.g.  `.ai/pipelines.md` — "don't change the state of self.text_encoder", or
      (b) `N/A — <one-line reason this domain has no applicable decision>` if nothing in
          that file's rationale applies to your change.
    The checker verifies (a)-citations resolve against the *current* file content on
    main (not a hardcoded line number or heading anchor — those go stale when the file
    changes) — it does not verify the citation is the *right* one for your lines, or
    that your understanding is *correct*. That part is still the human reviewer's job.
  - My understanding: your own words, 1-2 sentences. This is what a reviewer, QA, or a
    PM skimming the PR reads to see what you believe holds — write it so someone who
    didn't read the code could still evaluate it.

The footer line below is for humans skimming the PR (PM / DevOps) — a quick "did this
cover everything" glance. It is NOT what the check trusts; the check recomputes touched
vs. declared domains itself from the diff and the table above.
-->

<!-- decision-declaration:start -->
## Decision Declaration

| Domain | Decision I'm relying on | My understanding |
|---|---|---|
| pipelines | `.ai/pipelines.md` — "don't change the state of self.text_encoder" | I'm not mutating any registered component in place; the attention-processor swap I added saves and restores the original processor before returning, same as the PAG pattern. |
| models | N/A — this PR only touches pipeline code, no model-level changes | |

**Domains touched:** pipelines · **Declared:** pipelines · **Status:** ✅
<!-- decision-declaration:end -->
# throwaway line to test path-filter behavior
