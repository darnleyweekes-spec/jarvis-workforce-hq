# ALPHA capability stack

All 13 requested user forks are pinned as Git submodules. The capability
registry distinguishes source availability from a verified library install.
None is marked as a connected production executor.

| Component | ALPHA role | Local result | Remaining setup |
|---|---|---|---|
| Maxun | Structured web extraction | Source pinned | Docker, database services, robot configuration |
| Browser Use | Browser task automation | Fork installed; import passed | Chromium download failed; model connection |
| Langflow | Workflow authoring | Frozen workspace installed; import passed | Approved flows, model connections |
| Supabase | Database, auth, storage | Source pinned; current self-host docs reviewed | Docker, deployment, secrets and access policies |
| Crawl4AI | Research page extraction | Fork installed; import and adapter tests passed | Chromium download failed; live browser crawl untested |
| Dify | App workflows | Source pinned | Docker, model connections, workflows |
| J.P. Morgan Python Training | Python learning | Locked environment installed; imports passed | API key for external financial-data exercises |
| ComfyUI | Visual production | CPU runtime installed; CLI and local API passed | Model weights; no generation test |
| AnythingLLM | Document knowledge workspace | Source pinned | Docker or desktop runtime, document/model workspace |
| LibreChat | Conversation interface | Source pinned | MongoDB, model connections, app deployment |
| Handy | Voice input | Source pinned | Desktop OS, native build tools and microphone permissions |
| Chatterbox | ECHO speech output | CPU fork installed; import passed | Model weights; no synthesis test |
| Recordly | Demo screen recording | Source pinned | Desktop capture permissions and native Electron helpers |

## Reproduce source checkout

From a clone of the integration branch:

```bash
git submodule update --init --recursive
```

Every submodule commit is also recorded in `stack-sources.json` and
`capabilities.json`. Original licenses stay in the source repositories. Do not
update a fork automatically during a mission.

## Reproduce compatible Python environments

Requires Python 3.12 and `uv`. Use a separate environment per component:

```bash
uv venv .venv-browser-use
uv pip install --python .venv-browser-use/bin/python -r integrations/locks/browser-use.txt
uv venv .venv-crawl4ai
uv pip install --python .venv-crawl4ai/bin/python -r integrations/locks/crawl4ai.txt
uv venv .venv-python-training
uv pip install --python .venv-python-training/bin/python -r integrations/locks/python-training.txt
uv venv .venv-chatterbox
uv pip install --python .venv-chatterbox/bin/python -r integrations/locks/chatterbox.txt
uv venv .venv-comfyui
uv pip install --python .venv-comfyui/bin/python -r integrations/locks/ComfyUI.txt
```

CPU Torch wheel pins use the official PyTorch CPU index. Add
`--extra-index-url https://download.pytorch.org/whl/cpu` when replaying the
ComfyUI and Chatterbox lockfiles. Chatterbox's transitive Perth source commit is
recorded in its lockfile rather than left on a moving branch.

Langflow uses its own frozen workspace and local packages:

```bash
cd integrations/vendor/langflow
uv sync --frozen --no-dev
```

J.P. Morgan lessons are in `integrations/vendor/python-training/notebooks`.
This is educational course content, not an autonomous agent or trading system.

The Playwright Chromium download returned invalid/truncated ZIP content on
this host. After network access is fixed, rerun:

```bash
.venv-crawl4ai/bin/python -m playwright install chromium
```

Verify a local browser crawl before enabling real research missions. Do not
reuse personal browser sessions during installation.

## ALPHA handoff

`alpha-runtime/capability_registry.py` validates commit pins and prepares scoped
mission packets. A mission must explicitly allow `<capability-id>.prepare`.
Prepared packets retain constraints, evidence, mission state and remaining
setup. They do not execute tools or change approvals.

```python
from capability_registry import prepare_capability
packet = prepare_capability(store, mission_id, 'langflow')
```

`crawl4ai_adapter.py` supplies one bounded read-only extraction function for
hosts using the Crawl4AI environment. It requires `crawl4ai.read` in the task,
an explicit HTTPS host scope, a timeout and an output limit. Returned evidence
records the observed page content, source URL and retrieval time. Website
claims are not independently verified facts just because they were extracted.
Live browser crawling remains blocked by the failed Chromium download.

ALPHA keeps orchestration, provider routing, SQLite mission state, independent
verification and approval ownership. These forks do not replace those controls.
Separate host adapters and approved backend configuration are required before
service APIs become executable tools. Supabase is not substituted for the
existing mission ledger, and no database schema or hosted account was changed.

## Verification

```bash
python3 -m unittest discover -s alpha-runtime -p 'test_*.py' -v
.venv-crawl4ai/bin/python -m unittest discover -s alpha-runtime -p 'test_crawl4ai_adapter.py' -v
python3 alpha-runtime/capability_registry.py
```

Package-specific tests skip when their optional environment is absent. This
report records imports, command checks and host blockers. No paid
model calls, external sends, voice cloning, desktop recordings or production
deployments were used as installation tests.
