# OpenHands in ALPHA

## Installed component

`openhands-canvas/` pins the user's OpenHands fork at
`56638693908b8ac83a2fa3bde6eb6c33aae37f4b` (Agent Canvas 1.10.0, MIT).
This fork is a control interface. Its OpenHands Agent Server is a separate
runtime dependency, pinned by the fork to 1.40.1. It is not the older Python
OpenHands monolith.

## Source installation

Requires Node >=22.12 and npm. From the ALPHA root:

```bash
git submodule update --init integrations/openhands-canvas
cd integrations/openhands-canvas
npm ci --ignore-scripts --no-audit --no-fund
VITE_DO_NOT_TRACK=1 VITE_ENABLE_BROWSER_TOOLS=false npm run build
```

Serve the installed interface without starting a host-access agent:

```bash
node scripts/static-server.mjs --host 127.0.0.1 --port 3001 --dir build
```

This serves the interface only. Coding requires a configured isolated Agent
Server and a model. Do not use the full local launcher on a credential-bearing
host: its default agent can execute shell commands and access the host files.
Connect an isolated backend from Canvas settings. Never embed credentials in
public frontend builds. Do not start scheduled automations as part of setup.

## Mission handoff

A mission must allow `openhands.prepare`. Export one mission:

```bash
python3 alpha-runtime/openhands_handoff.py \
  --ledger /private/alpha/missions.sqlite3 \
  --mission mission-123 --workspace /private/sandbox/project
```

Pass the resulting prompt to Canvas only after checking its scoped evidence and
project path. The path identifies intended scope; it is not a sandbox boundary.
Use a dedicated container or VM. The handoff never sends an API request, starts
an agent, changes approvals, or marks mission criteria complete.

OpenHands prepares code and test artifacts. ALPHA's independent verifier must
check them, attach claim-evidence contracts, and obtain approval for any
consequential action. The integration does not automatically import success
claims, publish code, deploy Sites, send outreach, or replace model routing.

## Checks

```bash
python3 -m unittest discover -s alpha-runtime -p 'test_*.py' -v
```

The handoff tests check mission isolation, read-only ledger behavior, tool
permission denial, and invalid-ledger rejection. Agent-server/model execution
is not tested without an isolated configured backend.

The additional source catalog is documented in `STACK.md`. These tools remain
optional mission-scoped components rather than one shared dependency environment.
