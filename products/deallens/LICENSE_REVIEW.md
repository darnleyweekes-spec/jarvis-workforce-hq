# DealLens Fork License Review

This is an engineering/commercial-use screening note, not legal advice. DealLens v0.2 does not copy code from the candidate forks below.

## Reviewed

### LiteLLM
The fork's top-level `LICENSE` states that content outside restricted/enterprise directories is available under the MIT License, while enterprise content is separately licensed.

**DealLens rule:** permissible candidate for a later dependency only from the MIT-licensed portion, with required copyright/license notices preserved. Do not copy from enterprise-restricted paths.

### Firecrawl
The fork's top-level `LICENSE` is GNU Affero General Public License v3 (AGPL-3.0).

**DealLens rule:** do not embed or modify Firecrawl source inside a closed proprietary DealLens service without a deliberate AGPL compliance/legal decision. Prefer a separately operated service/API or another permissively licensed implementation if proprietary distribution is required.

### n8n
The fork's `LICENSE.md` uses the Sustainable Use License for non-enterprise code and limits use/modification to internal business purposes or non-commercial/personal use, with separate restrictions for enterprise files.

**DealLens rule:** do not copy, bundle, white-label, or redistribute n8n code as part of the commercial DealLens product under the current plan. If used operationally, confirm the intended deployment is within the license or obtain the appropriate commercial license.

## Pending before code reuse

The following are integration candidates only until their exact current license and relevant directory-level exceptions are checked: `activepieces`, `paperless-ngx`, `markitdown`, `anything-llm`, `onyx`, `crawl4ai`, `documenso`.

## Jarvis licensing gate

1. No fork source enters DealLens solely because it exists in the user's GitHub account.
2. Prefer API boundaries and independent implementations over source copying.
3. Record license, version/commit, relevant exceptions, notice requirements, and commercial-use constraints before adoption.
4. Treat directory-level enterprise exceptions as separate licenses.
5. Re-review licenses before release because upstream terms can change.
