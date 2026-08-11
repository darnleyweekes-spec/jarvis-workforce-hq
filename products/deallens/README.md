# DealLens

DealLens is a human-supervised AI diligence workspace for search funds, independent sponsors, boutique M&A advisors, family offices, and small private-equity teams.

## Core promise

Upload a CIM, financial exports, customer concentration data, contracts, and supporting documents. DealLens prepares a first-pass diligence packet with source-linked observations, deterministic financial checks, red flags, management questions, and an investment-committee memo draft.

## MVP guardrails

- AI may summarize and classify evidence, but it must not invent financial results.
- Financial ratios and concentration metrics are calculated deterministically from supplied structured data.
- Every material observation should point back to source evidence.
- Human approval is required before any investment recommendation, client delivery, external outreach, or consequential action.
- DealLens is decision support, not investment, legal, tax, or accounting advice.

## Initial workflow

1. Create a deal workspace.
2. Upload PDF/TXT/CSV/XLSX diligence files.
3. Extract readable text and structured tables.
4. Run deterministic financial and concentration checks.
5. Run red-flag and evidence discovery.
6. Generate management questions.
7. Assemble an IC memo draft.
8. Human reviewer approves, edits, or rejects findings.

## Fork strategy

The first commercial MVP is a thin proprietary layer. Existing forks are treated as optional infrastructure/integration candidates rather than copied wholesale until license review is complete.

Likely components/patterns:
- `paperless-ngx` / `markitdown`: document ingestion patterns
- `anything-llm` / `onyx`: retrieval and knowledge-workspace patterns
- `firecrawl` / `crawl4ai`: public-company and market research
- `n8n` / `activepieces`: workflow automation
- `litellm`: model routing
- `documenso`: document workflow patterns
- Jarvis workforce: orchestration, review, and human-approval gates

## Founding offer

**DealLens Express — $1,500 per deal**

First-pass diligence packet for a lower-middle-market acquisition target, including:
- executive deal snapshot
- source-backed red flags
- customer concentration review
- financial sanity checks
- management diligence questions
- IC memo draft

The service model comes first. SaaS packaging follows after repeated workflows are validated with paying users.
