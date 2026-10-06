# Listmonk in ALPHA

User fork: https://github.com/darnleyweekes-spec/listmonk
Pinned source: `0808fe5a83e9abb5f3f738a4dd6ead1c3ed2afe1`
Path: `integrations/vendor/listmonk`. Original licenses remain in the fork.

Source checkout and ALPHA registration are complete. The service was not built
or started: this host lacks Go and PostgreSQL. The pinned source requires
Go 1.26.1. Its frontend build also needs Node.js and Yarn.

## ALPHA use

Use `prepare_capability(store, mission_id, 'listmonk')` with the explicit
`listmonk.prepare` permission to prepare a scoped campaign brief. It preserves
mission constraints and evidence without changing mission state or sending mail.
Execution is disabled until a service adapter and configuration are verified.

Keep existing project outreach in personal Gmail with the Prime24AI mention.
This integration does not change that route or authorize batches. No contacts
were imported, SMTP configured, campaign started or message sent.

## Docker-free installation

The official standalone binary needs PostgreSQL 12 or later. The upstream
release binary is an alternative distribution, not a build of this pinned fork.
For the user's Intel Mac, select Darwin amd64 from the official release page:
https://listmonk.app/

On a persistent host with PostgreSQL configured:

1. Download and extract the appropriate official release.
2. Run `./listmonk --new-config` in a dedicated directory.
3. Set the database connection and bind the app to loopback for local use.
4. Run `./listmonk --install` against a new, dedicated database.
5. Run `./listmonk` and configure the admin account.
6. Configure SMTP only after the sending identity and approval process are set.
7. Test against a local mock SMTP server before any real campaign.

Never commit live config, database passwords, SMTP secrets or subscriber data.
Database initialization was not run here.

Installation reference: https://listmonk.app/docs/installation/

## Source checkout

```bash
git submodule update --init integrations/vendor/listmonk
```
