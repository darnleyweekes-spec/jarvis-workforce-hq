# ALPHA operation status

The source stack is merged. This host is temporary; it is not a persistent deployment host.

## Tested local alternatives

- Chatterbox: `local_speech_adapter.speak` uses FFmpeg Flite and a stock voice. A real WAV check passed. Requires `speech.local.write`. No cloned voice or model download.
- AnythingLLM document retrieval: `local_knowledge_adapter.search_documents` uses SQLite FTS5 over explicitly supplied documents. Results retain source references. Requires `knowledge.local.read`. No embeddings, autonomous answers, hosted database or auth service.
- Maxun/Crawl4AI static extraction: `static_web_adapter.extract_static` uses bounded HTTPS reads, host scope, robots policy and rejects redirects. Requires `web.static.read`. Unit tests passed; live use is blocked here by DNS. It does not run JavaScript.
- Web research in Work: the web-search connector successfully retrieved prime24ai.com. It is available to the assistant, not a callable backend in the standalone ALPHA repository.
- Dify/Langflow orchestration: existing ALPHA mission routing, ledger, verification and approvals remain usable. This is not a replacement for either visual flow builder.
- Supabase: keep the existing SQLite mission ledger for local projects. This does not provide Supabase auth, storage, realtime or hosted Postgres.
- LibreChat: use this Work chat for projects; no separate LibreChat server is active.
- ComfyUI: CPU server smoke passed previously; actual model generation is pending. Work image generation is an available assistant tool, not a connected ALPHA server.
- Handy/Recordly: this host has no desktop or microphone. Typed requests and uploaded recordings are usable inputs here. They do not replace recording or live transcription.
- OpenHands: Canvas and scoped handoff are installed. Coding can use Work's execution tools. No isolated Agent Server or model-backed agent run is active.
- Python training: installed notebooks and tools remain available.

## Deployment gates

Docker is absent and this process has no kernel capabilities or Docker socket. No remote deployment host is configured. Installing a Docker CLI alone cannot supply container isolation.

No provider API key is configured. Do not paste secrets in chat or commit them. Configure keys through the deployment platform's secret settings when a host is selected.

Both full Chromium and headless-shell downloads returned invalid archives. Native browser automation remains blocked; use Work web search for current research.

The first Langflow launch was blocked by automatic review because it attempted Scarf telemetry. A safer launch sets `DO_NOT_TRACK=true`, `LANGFLOW_DO_NOT_TRACK=true` and `LITELLM_LOCAL_MODEL_COST_MAP=true`, uses Uvicorn directly to avoid the restricted Gunicorn control socket, and binds only to loopback with generated temporary credentials. The safer launch passed `/health` with HTTP 200 and shut down cleanly. No live provider flow has been tested.

Do not mark these source components as executable production tools until their own service, credentials and end-to-end checks pass. Prepared capability packets remain read-only.

## Checks

Run the ALPHA suite with `.venv-semantica/bin/python -m unittest discover -s alpha-runtime` and the Crawl4AI suite in its own environment. Local alternatives have permission, output-limit, robots, citation and artifact checks. The speech check synthesizes and opens a real WAV file.
