# ALPHA Mission Control

ALPHA Mission Control is a human-supervised, fork-powered AI action engine. A visitor provides a real objective; ALPHA classifies the mission, routes it to the smallest useful specialist team, selects candidate open-source capabilities, and returns a practical execution brief with explicit approval boundaries.

## Public v1

The first public release is intentionally lightweight and safe:

- interactive mission intake in the browser
- six mission modes: operations, research, product/engineering, growth, digital exposure/security, and career/opportunity
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
