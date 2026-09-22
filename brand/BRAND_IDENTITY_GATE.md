# ALPHA Brand Identity Gate

## Purpose

Use this gate before changing a project's homepage, offer, proposal, outreach angle, visual identity, or first client interaction. It converts brand work into one observable implementation decision. It is not permission to invent customer sentiment.

## Mission routing

- **CONDUCTOR** opens the project record and prevents duplicate work.
- **SCOUT** gathers attributable customer/prospect language and identifies the visible perception gap.
- **FORGE** selects one or two relevant identity perspectives and defines the exact move.
- **PULSE** defines the 30-day measure, source, owner, target, and attribution limits.
- **SCRIBE** records the approved decision and the words or behavior to stop using.
- **ALPHA** resolves conflicts and requires human approval before publication or production change.

## Required sequence

1. **Perception gap** — Compare verbatim, attributable market language with the desired reputation. Name one gap and its specific cause. If evidence is absent, return `EVIDENCE_REQUIRED`.
2. **Identity perspective** — Choose only the most relevant one or two: product, organization, person, or symbol. Every choice must connect directly to the gap.
3. **Value** — State functional, emotional, and self-expressive value. Functional value alone cannot pass. Mark unverified emotional language as a hypothesis and test it.
4. **Exact move** — Change one highest-visibility touchpoint first. Record the concrete action, what must stop, and the 30-day evidence threshold.

## Evidence contract

Each current-image observation must include:

- verbatim customer or prospect language
- source or evidence reference
- observation date
- touchpoint where the perception appeared

Analytics may show behavior but cannot alone establish how people describe the brand. Founder preference is a desired-identity input, not evidence of current perception.

## Decision states

- `EVIDENCE_REQUIRED` — no usable current-perception evidence; do not diagnose the gap.
- `INCOMPLETE` — evidence exists, but the identity, value, move, or metric is underspecified.
- `READY_FOR_HUMAN_REVIEW` — all fields pass; no external or production action has happened yet.
- `APPROVED_FOR_TEST` — the owner has approved the single reversible move and measurement plan.
- `KEEP`, `ITERATE`, or `REVERT` — assigned after the 30-day review based on the agreed evidence.

## Project application

`project-brand-registry.json` contains the active portfolio and only seeds desired identity and known functional value. Every project starts at `EVIDENCE_REQUIRED` until real language is added. This avoids turning internal positioning into fake market proof.

Run the local validator:

```bash
node brand-identity-gate.test.js
```

## Exact output

- Current Image
- Desired Identity
- The Gap
- What's Causing It
- Most Relevant Perspective(s)
- Functional Benefit
- Emotional Benefit
- Self-Expressive Benefit
- Strongest Benefit and why
- The Exact Move
- Where It Happens First
- Stop Saying or Doing This
- 30-Day Evidence: metric, source, owner, target, window
- Approval status

