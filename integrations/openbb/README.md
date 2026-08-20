# OpenBB integration for ALPHA

This integration exposes OpenBB as a read-only finance and market intelligence capability for ALPHA.

## Safety boundary

- Research and analysis only.
- No brokerage connection or order execution.
- No autonomous trading actions.
- Market outputs are evidence inputs, not financial advice.
- Consequential actions remain behind ALPHA's human approval boundary.

## Local install

```bash
python3 -m venv ~/.alpha/openbb-env
source ~/.alpha/openbb-env/bin/activate
python -m pip install --upgrade pip
pip install -r integrations/openbb/requirements-openbb.txt
openbb-build
```

## Smoke test

```bash
python integrations/openbb/alpha_openbb.py quote AAPL
python integrations/openbb/alpha_openbb.py history AAPL --start-date 2026-01-01
```

## ALPHA routing contract

Route finance intents such as market price, historical price, company fundamentals, macroeconomic research, FX, crypto, fixed income, and screening to this capability when current financial data is required.

The initial adapter exposes equity quote and historical-price operations. Additional OpenBB endpoints should be added narrowly as ALPHA needs them rather than granting a generic unrestricted call surface.

The adapter returns JSON with:

- `capability`: `openbb_finance`
- `read_only`: `true`
- `query`
- `data`
- `warnings`

Provider credentials should be supplied through environment variables supported by the selected OpenBB provider. Do not commit API keys.
