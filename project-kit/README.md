# ALPHA project contract

ALPHA should be a reusable operating pattern across projects, not a collection of
unrelated agents. This kit defines the same first questions for every product:
customer, painful problem, why now, narrow workflow, baseline, target, proof,
and approval boundary. `projects.json` contains planning contracts for the ten
active products in the brand registry. The overlapping legacy AgentForce HQ
entry is intentionally omitted; it is marked consolidate or retire there.

These entries are **planning hypotheses**, not verified customer evidence or
installed integrations. All `connected_tools` arrays are empty. The existing
public Mission Lab and project Sites remain separate from the Python runtime.

## Start a new idea

```bash
python3 project-kit/project_contract.py new sample-idea 'Sample Idea' > sample-idea.json
python3 project-kit/project_contract.py check sample-idea.json
```

The check will fail until the missing fields are filled. Add attributable
evidence for the problem and baseline before calling it a validated business.
For an existing contract run:

```bash
python3 project-kit/project_contract.py check project-kit/projects.json
python3 -m unittest discover -s project-kit -p 'test_*.py' -v
```

`mission_from_profile` creates a scoped `MissionRequest` with no tool access,
an explicit success check, and prohibited external actions. A project-specific
host can later inject an authenticated adapter after its own integration review.
The contract does not grant permissions or create a production API.

## Apply to a project

1. Inspect its current source, user flow, data, and working behavior.
2. Fill the contract from observed evidence. State hypotheses as hypotheses.
3. Run one bounded mission with a before-and-after measure, segmented where
   volume or customer type could hide a failure.
4. Add a narrow adapter only if the same task repeats and the result can be
   independently verified. Keep customer-facing sends and consequential
   changes under authenticated human approval.
5. Record setup hours, review burden, incidents, and business outcomes. Stop
   or revise when the narrow pilot does not improve the target.

Priority: lead follow-up in Agents and verified incident handling in
PrimeSignal are testable workflows. Learn, PitchMe, BuyerCue, Paws & Power,
ReviewLift, MedBill Scout, and CredentialFlow need product-specific measures
and boundaries before they share live ALPHA tools. A new idea starts as a
contract, not a new site or agent roster.
