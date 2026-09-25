# ALPHA Mission Control

ALPHA Mission Control is a human-supervised, fork-powered AI action engine. A visitor provides a real objective; ALPHA classifies the mission, routes it to the smallest useful specialist team, selects candidate open-source capabilities, and returns a practical execution brief with explicit approval boundaries.

## Public v1

The first public release is intentionally lightweight and safe:

- interactive mission intake in the browser
- seven mission modes: operations, research, product/engineering, brand identity/positioning, growth, digital exposure/security, and career/opportunity
- specialist-agent routing
- candidate GitHub fork selection
- five-step execution plans
- explicit human-approval gates
- copyable and downloadable mission briefs
- no mission text sent to a backend in the public demo

## ALPHA network

ALPHA is the primary orchestrator and final AI synthesis point. Specialist roles are activated based on the mission rather than running every agent on every task.

Representative routing includes:

- **Planning + product:** VISION, PAM
- **Research + evidence:** ROSALIND, MR. HOLMES, NEIL
- **Engineering + ML/LLM:** FRED, BOB, HAL, JAN
- **Operations + reliability:** TED
- **Security + governance:** BENICIO, BILLY, SAM, PAUL
- **Strategy:** MARK

Human approval remains required for consequential actions.

## Fork capability map

The repository inventory supplies reusable capabilities rather than one monolithic dependency:

- **Research + knowledge:** Firecrawl, Onyx, open-notebook, MarkItDown, Karakeep, Papermark
- **Agent orchestration:** Dify, Langflow, Flowise, Ruflo, Hermes Agent, Prime Agent
- **Automation + CRM:** n8n, Activepieces, Twenty, listmonk, Postiz
- **Model infrastructure:** llama.cpp, vLLM, LiteLLM, AirLLM, AutoTrain
- **OSINT + trust:** Sherlock, theHarvester, user-scanner, CrowdSec
- **Growth + distribution:** open-seo, marketingskills, Agent-Reach, MoneyPrinterV2

Forks are candidate components. Production integration requires license, dependency, secrets, data-flow, and permission review before use.

## Architecture direction

The browser Mission Lab is the public front door. Later phases connect approved missions to backend research, document intelligence, workflow automation, CRM state, and model routing. See `ALPHA_ARCHITECTURE.md` for the staged design.

## Safety model

ALPHA follows a context-first, least-privilege model. Publishing, payments, outreach, production deployments, destructive changes, sensitive security activity, or other consequential actions require explicit human authorization. Security workflows must remain limited to owned or explicitly authorized scope.


## Current capability boundary

The public Mission Lab is a deterministic local planning demo, not a connected multi-agent executor. It classifies a mission and prepares a first-pass brief; it does not yet run specialist agents, persist a mission ledger, or verify real-world outcomes. Those capabilities remain gated roadmap work.

## Brand identity gate

The `brand/` directory adds ALPHA's evidence-first brand decision workflow for Prime24AI and the active project portfolio. It blocks perception claims when customer/prospect evidence is missing, limits identity selection to the relevant Aaker perspective(s), requires functional plus emotional or self-expressive value, and permits only one measurable 30-day move after human approval.

Run its validator with:

```bash
node brand/brand-identity-gate.test.js
```


## Executable runtime core

`alpha-runtime/` contains a provider-neutral Python execution core with SQLite persistence, hash-chained append-only events, evidence provenance, scoped specialist contracts, independent verification, human approval bound to exact action payloads, and fail-closed idempotent action reservations. Run its standard-library test suite with:

```bash
python3 -m unittest discover -s alpha-runtime -p 'test_*.py' -v
```

This is an executable core, not yet the connected production ALPHA service: there is no API server, authentication, tenant isolation, model/provider adapter, hosted storage, or Sites UI connection. See `alpha-runtime/README.md` for the integration contract and deployment limitations.

## Project contracts

`project-kit/` contains scoped planning contracts for ten current projects and a
new-idea template. It asks for the customer, problem, workflow, evidence,
baseline, target, and approval boundary before a mission is prepared. It grants
no tool access and makes no claim that the Sites are connected to ALPHA. Run
`python3 project-kit/project_contract.py check project-kit/projects.json` and
see `project-kit/README.md` for the onboarding workflow.
