# Penpot in ALPHA

The user fork is pinned at `9d08e26cb3d0ed003a5cf7df37adc778019bf75e`
in `integrations/vendor/penpot`. Original licenses remain in the fork.

ALPHA can prepare a design mission with
`prepare_capability(store, mission_id, 'penpot')` when the mission allows
`penpot.prepare`. The packet preserves objectives, criteria, constraints and
evidence. It does not create designs, connect an account or run MCP tools.

## Live editor

This host has no Docker daemon, persistent Postgres service or configured
Penpot workspace. Source registration is complete; the editor is not running.
The fork's development Compose file includes placeholder secrets and local-only
security settings. It is not a production deployment configuration.

Use a persistent container host and the official deployment guide:
https://help.penpot.app/technical-guide/getting-started/docker/

A hosted alternative is https://design.penpot.app/ . No account was created
or connected here.

## MCP

The pinned fork contains the official MCP server and browser plugin in `mcp/`.
They require an open Penpot design file and a connected plugin. MCP can execute
code and change designs; keep operations within an approved project, verify
changes and preserve ALPHA approval rules. No MCP server was registered in
Work and no design workspace was changed.

## Source checkout

```bash
git submodule update --init integrations/vendor/penpot
```

## Local validation

MCP dependencies installed from the frozen lockfile with pnpm 11.25.0
(the fork declares pnpm 12.5.1). Install scripts were disabled.
The common package, MCP server and browser plugin built successfully.
All 32 server tests passed using `node --import tsx --test src/*.test.ts`.
The normal tsx CLI test command was blocked by restricted Unix sockets;
the direct Node test runner avoids that CLI control socket.
No live plugin connection or complete Penpot editor build was tested.
