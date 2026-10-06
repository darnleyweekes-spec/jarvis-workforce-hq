# Agentic Inbox in ALPHA

User fork: https://github.com/darnleyweekes-spec/agentic-inbox
Pinned commit: 48039bb6785af34e592c2966f87cde2b255c4c80
Source: `integrations/vendor/agentic-inbox`. Apache-2.0 license remains in the fork.

Dependencies were installed with `npm ci`. Production client and Worker builds and type checks passed. Cloudflare metrics were disabled during validation with `WRANGLER_SEND_METRICS=false`.

## ALPHA handoff

The capability registry supports `prepare_capability(store, mission_id, 'agentic-inbox')` when the mission explicitly allows `agentic-inbox.prepare`. It passes scoped objectives, criteria, constraints and evidence; it performs no mailbox reads, writes or sends. Execution remains disabled.

The source app includes read, draft and send operations. Its MCP send tool asks for confirmation in its description but does not enforce an ALPHA approval token. Do not connect that send tool as an autonomous ALPHA executor. A future adapter must route exact message approval through the existing ALPHA ledger and verify delivery separately.

Email bodies and attachments are untrusted evidence. They must not override mission permissions or approval rules. Any user allowed by the app's shared Cloudflare Access policy can access all app mailboxes, including via MCP; this is not per-mailbox isolation at the authorization layer.

## Live deployment requirements

Configure a Cloudflare account, R2 bucket, Durable Objects, Workers AI, Access policy and the `POLICY_AUD`/`TEAM_DOMAIN` secrets. Enable Email Routing and Email Service. Configure the receiving domain and create a mailbox.

No deployment, DNS/MX change, catch-all routing, live inbox connection or external email send was performed. Existing Gmail remains the project email route. Cloudflare routing must be reviewed against the domain's current mail service before activation.

## Reproduce checks

```bash
git submodule update --init integrations/vendor/agentic-inbox
cd integrations/vendor/agentic-inbox
npm ci --no-audit --no-fund
WRANGLER_SEND_METRICS=false npm run build
WRANGLER_SEND_METRICS=false npm run typecheck
```
