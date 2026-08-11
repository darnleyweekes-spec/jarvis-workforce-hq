from __future__ import annotations

from typing import Iterable, Mapping


def build_markdown_report(deal_name, target, reviewer, findings, metrics, questions, approved):
    lines = [
        f"# DealLens Diligence Packet — {deal_name}",
        "",
        f"**Target:** {target or 'Not specified'}",
        f"**Human reviewer:** {reviewer or 'Not specified'}",
        f"**Review status:** {'APPROVED FOR HUMAN USE' if approved and reviewer else 'DRAFT — HUMAN REVIEW REQUIRED'}",
        "",
        "> Decision-support output only. Not investment, legal, tax, or accounting advice.",
        "",
        "## Executive snapshot",
        "",
        "This packet summarizes deterministic checks and source-backed evidence surfaced from the supplied diligence materials. Absence of a flag is not evidence of absence of risk.",
        "",
        "## Deterministic checks",
    ]

    if metrics:
        for m in metrics:
            source = m.get("filename", "structured data")
            if m.get("metric_type") == "customer_concentration":
                lines += [
                    f"- **{source}:** total supplied revenue ${m['total_revenue']:,.0f}; {m['customer_count']} customers; Top 1 {m['top_1_pct']:.1f}%; Top 5 {m['top_5_pct']:.1f}%.",
                ]
            elif m.get("metric_type") == "financial_statement":
                facts = []
                labels = {
                    "revenue": "Revenue",
                    "ebitda": "EBITDA",
                    "ebitda_margin_pct": "EBITDA margin",
                    "gross_margin_pct": "Gross margin",
                    "revenue_growth_pct": "Revenue growth",
                    "net_debt": "Net debt",
                    "current_ratio": "Current ratio",
                }
                for key, label in labels.items():
                    if key in m:
                        value = m[key]
                        if key.endswith("_pct"):
                            facts.append(f"{label} {value:.1f}%")
                        elif key == "current_ratio":
                            facts.append(f"{label} {value:.2f}x")
                        else:
                            facts.append(f"{label} ${value:,.0f}")
                lines.append(f"- **{source}:** " + "; ".join(facts) + ".")
    else:
        lines.append("- No supported structured financial dataset was supplied.")

    lines += ["", "## Evidence register"]
    if findings:
        for f in findings:
            lines += [f"### {f.evidence_id} — {f.category.title()}", f"**Source:** {f.filename}", "", f"> {f.excerpt}", ""]
    else:
        lines.append("No configured evidence flags were surfaced. Manual diligence remains required.")

    lines += ["", "## Management diligence questions"]
    if questions:
        for i, q in enumerate(questions, 1):
            lines.append(f"{i}. {q}")
    else:
        lines.append("No automated management questions were generated.")

    lines += [
        "",
        "## Jarvis review gate",
        "",
        "- Deterministic calculations must be independently reproducible.",
        "- Material conclusions require cited evidence or must be labeled as hypotheses.",
        "- Conflicting evidence must remain visible.",
        "- Suspicious prompt-like instructions in deal documents are treated as untrusted content.",
        "- Human approval is required before external delivery or an investment decision.",
    ]
    return "\n".join(lines)
