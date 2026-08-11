import io
import re
from dataclasses import dataclass
from typing import List

import pandas as pd
import streamlit as st
from pypdf import PdfReader

from finance import customer_concentration, financial_statement_metrics
from reporting import build_markdown_report
from security import assess_file, prompt_injection_hits, sanitize_text

st.set_page_config(page_title="DealLens", page_icon="📊", layout="wide")

RED_FLAG_PATTERNS = {
    "customer concentration": [r"customer concentration", r"top customer", r"largest customer"],
    "churn / retention": [r"churn", r"retention", r"renewal rate", r"logo retention"],
    "litigation": [r"litigation", r"lawsuit", r"claim against", r"legal proceeding"],
    "debt / covenant": [r"covenant", r"default", r"debt facility", r"credit agreement"],
    "related-party": [r"related party", r"related-party"],
    "revenue recognition": [r"revenue recognition", r"deferred revenue", r"unbilled revenue"],
    "working capital": [r"working capital", r"accounts receivable", r"accounts payable"],
    "key-person dependency": [r"key person", r"key-person", r"founder dependency", r"dependent on .*founder"],
    "change of control": [r"change of control", r"change-in-control"],
}


@dataclass
class Evidence:
    evidence_id: str
    category: str
    filename: str
    excerpt: str


def extract_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return sanitize_text("\n".join((page.extract_text() or "") for page in reader.pages))


def read_upload(uploaded_file):
    raw = uploaded_file.getvalue()
    assessment = assess_file(raw)
    if not assessment.allowed:
        return {"kind": "blocked", "assessment": assessment, "value": None}
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        value = extract_pdf(raw)
        return {"kind": "text", "assessment": assessment, "value": value, "injection_hits": prompt_injection_hits(value)}
    if name.endswith((".txt", ".md")):
        value = sanitize_text(raw.decode("utf-8", errors="ignore"))
        return {"kind": "text", "assessment": assessment, "value": value, "injection_hits": prompt_injection_hits(value)}
    if name.endswith(".csv"):
        return {"kind": "table", "assessment": assessment, "value": pd.read_csv(io.BytesIO(raw))}
    if name.endswith((".xlsx", ".xls")):
        return {"kind": "table", "assessment": assessment, "value": pd.read_excel(io.BytesIO(raw))}
    return {"kind": "unknown", "assessment": assessment, "value": None}


def find_evidence(filename: str, text: str, start_index: int) -> List[Evidence]:
    findings = []
    compact = re.sub(r"\s+", " ", text)
    counter = start_index
    for category, patterns in RED_FLAG_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, compact, re.IGNORECASE)
            if match:
                counter += 1
                start = max(0, match.start() - 180)
                end = min(len(compact), match.end() + 260)
                findings.append(Evidence(f"E{counter:03d}", category, filename, compact[start:end].strip()))
                break
    return findings


def management_questions(findings, metrics):
    qs = []
    categories = {f.category for f in findings}
    mapping = {
        "customer concentration": "What contractual, renewal, pricing, and relationship risks exist for the largest customers, and how portable are those relationships after a change of control?",
        "churn / retention": "Provide cohort-level gross and net retention by customer segment for the last 24–36 months and explain the primary drivers of churn.",
        "litigation": "List all current, threatened, and recently resolved legal matters, expected exposure, insurance coverage, and management's assessment of materiality.",
        "debt / covenant": "Provide all debt agreements, covenant calculations, amendment history, and any known or projected covenant pressure under the transaction case.",
        "related-party": "Identify all related-party arrangements and quantify the normalized arm's-length cost or revenue impact after closing.",
        "change of control": "Identify every agreement with change-of-control consent, termination, repricing, acceleration, or assignment provisions and quantify the exposure.",
    }
    for category, question in mapping.items():
        if category in categories:
            qs.append(question)
    for m in metrics:
        if m.get("metric_type") == "customer_concentration":
            if m.get("top_1_pct", 0) >= 20:
                qs.append(f"The largest customer represents {m['top_1_pct']:.1f}% of supplied revenue. What is its renewal date, termination language, pricing history, and executive relationship ownership?")
            if m.get("top_5_pct", 0) >= 50:
                qs.append(f"The top five customers represent {m['top_5_pct']:.1f}% of supplied revenue. Show the downside case for loss or repricing of one or more of these accounts.")
        if m.get("metric_type") == "financial_statement":
            if m.get("revenue_growth_pct", 0) < 0:
                qs.append("Revenue declined versus the supplied prior period. Reconcile the decline by customer, product/service line, price, volume, and one-time items.")
            if m.get("current_ratio", 2) < 1:
                qs.append("The supplied current ratio is below 1.0x. Explain near-term liquidity, working-capital seasonality, and required cash at close.")
    return list(dict.fromkeys(qs))


st.title("DealLens")
st.caption("Human-supervised acquisition diligence. Deterministic calculations + source-backed evidence + reviewer gate.")

with st.sidebar:
    st.header("Deal workspace")
    deal_name = st.text_input("Deal name", value="Project Atlas")
    target = st.text_input("Target company", value="")
    reviewer = st.text_input("Human reviewer", value="")
    st.caption("Deal documents are treated as untrusted input. Embedded instructions never override DealLens/Jarvis rules.")

uploads = st.file_uploader(
    "Upload CIM, diligence documents, customer revenue exports, or financial statements",
    type=["pdf", "txt", "md", "csv", "xlsx", "xls"],
    accept_multiple_files=True,
)

all_findings = []
all_metrics = []
processed = []
security_warnings = []

if uploads:
    evidence_counter = 0
    for f in uploads:
        try:
            parsed = read_upload(f)
            assessment = parsed["assessment"]
            if parsed["kind"] == "blocked":
                security_warnings.append(f"{f.name}: blocked ({assessment.reason})")
                continue
            processed.append({"name": f.name, "kind": parsed["kind"], "sha256": assessment.sha256})
            if parsed["kind"] == "text":
                hits = parsed.get("injection_hits", [])
                if hits:
                    security_warnings.append(f"{f.name}: suspicious prompt-like instructions detected; content remains untrusted and is shown only as evidence.")
                findings = find_evidence(f.name, parsed["value"], evidence_counter)
                all_findings.extend(findings)
                evidence_counter += len(findings)
            elif parsed["kind"] == "table":
                for calculator in (customer_concentration, financial_statement_metrics):
                    metric = calculator(parsed["value"])
                    if metric:
                        metric["filename"] = f.name
                        all_metrics.append(metric)
        except Exception as exc:
            security_warnings.append(f"{f.name}: could not process safely ({type(exc).__name__}).")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Files processed", len(processed))
    col2.metric("Evidence flags", len(all_findings))
    col3.metric("Deterministic checks", len(all_metrics))
    col4.metric("Security warnings", len(security_warnings))

    if security_warnings:
        st.subheader("Security review")
        for warning in security_warnings:
            st.warning(warning)

    st.subheader("Deterministic financial checks")
    if all_metrics:
        for m in all_metrics:
            if m["metric_type"] == "customer_concentration":
                st.write(f"**{m['filename']}** — Revenue ${m['total_revenue']:,.0f} | Customers {m['customer_count']} | Top 1 {m['top_1_pct']:.1f}% | Top 5 {m['top_5_pct']:.1f}%")
            else:
                parts = []
                for key, label in [("revenue", "Revenue"), ("revenue_growth_pct", "Growth"), ("ebitda", "EBITDA"), ("ebitda_margin_pct", "EBITDA margin"), ("gross_margin_pct", "Gross margin"), ("net_debt", "Net debt"), ("current_ratio", "Current ratio")]:
                    if key in m:
                        value = m[key]
                        if key.endswith("_pct"):
                            parts.append(f"{label} {value:.1f}%")
                        elif key == "current_ratio":
                            parts.append(f"{label} {value:.2f}x")
                        else:
                            parts.append(f"{label} ${value:,.0f}")
                st.write(f"**{m['filename']}** — " + " | ".join(parts))
    else:
        st.info("For concentration use Customer + Revenue columns. For financial statements use Metric/Line Item + Current, optionally Prior.")

    st.subheader("Evidence register")
    if all_findings:
        for finding in all_findings:
            with st.expander(f"{finding.evidence_id} · {finding.category.title()} · {finding.filename}"):
                st.write(finding.excerpt)
    else:
        st.info("No configured evidence phrases were surfaced. This does not establish that the deal is low risk.")

    questions = management_questions(all_findings, all_metrics)
    st.subheader("Management diligence questions")
    if questions:
        for i, q in enumerate(questions, 1):
            st.write(f"{i}. {q}")
    else:
        st.write("No automated questions generated from the supplied materials.")

    st.subheader("Jarvis reviewer gate")
    calc_confirmed = st.checkbox("I independently checked the deterministic calculations against the source data.")
    evidence_confirmed = st.checkbox("I reviewed the cited source excerpts and did not treat unsupported AI inference as fact.")
    security_confirmed = st.checkbox("I reviewed security warnings and treated document instructions as untrusted content.")
    approved = bool(reviewer.strip() and calc_confirmed and evidence_confirmed and security_confirmed)
    if approved:
        st.success(f"Jarvis review gate passed for {deal_name} by {reviewer.strip()}.")
    else:
        st.info("External delivery remains locked until all reviewer checks are complete and a reviewer is named.")

    report = build_markdown_report(deal_name, target, reviewer, all_findings, all_metrics, questions, approved)
    st.download_button(
        "Download diligence packet (.md)",
        data=report,
        file_name=f"{re.sub(r'[^A-Za-z0-9_-]+', '_', deal_name).strip('_') or 'deallens'}_diligence_packet.md",
        mime="text/markdown",
        disabled=not approved,
    )

    with st.expander("File integrity register"):
        for item in processed:
            st.code(f"{item['name']} | {item['kind']} | SHA-256 {item['sha256']}")
else:
    st.info("Upload deal materials to begin first-pass diligence.")

st.divider()
st.caption("DealLens MVP v0.2 — calculations are deterministic; evidence extraction is source-linked; documents are untrusted; final decisions remain human-owned.")
