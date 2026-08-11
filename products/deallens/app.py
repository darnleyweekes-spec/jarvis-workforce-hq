import io
import re
from dataclasses import dataclass
from typing import List, Dict

import pandas as pd
import streamlit as st
from pypdf import PdfReader

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
}

@dataclass
class Evidence:
    category: str
    filename: str
    excerpt: str


def extract_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def read_upload(uploaded_file):
    raw = uploaded_file.getvalue()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        return {"kind": "text", "value": extract_pdf(raw)}
    if name.endswith(".txt") or name.endswith(".md"):
        return {"kind": "text", "value": raw.decode("utf-8", errors="ignore")}
    if name.endswith(".csv"):
        return {"kind": "table", "value": pd.read_csv(io.BytesIO(raw))}
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return {"kind": "table", "value": pd.read_excel(io.BytesIO(raw))}
    return {"kind": "unknown", "value": None}


def find_evidence(filename: str, text: str) -> List[Evidence]:
    findings = []
    compact = re.sub(r"\s+", " ", text)
    for category, patterns in RED_FLAG_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, compact, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 180)
                end = min(len(compact), match.end() + 260)
                findings.append(Evidence(category, filename, compact[start:end].strip()))
                break
    return findings


def concentration_metrics(df: pd.DataFrame) -> Dict[str, float]:
    normalized = {str(c).strip().lower(): c for c in df.columns}
    customer_col = normalized.get("customer") or normalized.get("customer_name") or normalized.get("name")
    revenue_col = normalized.get("revenue") or normalized.get("sales") or normalized.get("amount")
    if not customer_col or not revenue_col:
        return {}
    working = df[[customer_col, revenue_col]].copy()
    working[revenue_col] = pd.to_numeric(working[revenue_col], errors="coerce")
    working = working.dropna(subset=[revenue_col])
    grouped = working.groupby(customer_col, dropna=False)[revenue_col].sum().sort_values(ascending=False)
    total = float(grouped.sum())
    if total <= 0:
        return {}
    return {
        "total_revenue": total,
        "top_1_pct": float(grouped.head(1).sum() / total * 100),
        "top_5_pct": float(grouped.head(5).sum() / total * 100),
        "customer_count": int(grouped.shape[0]),
    }


def management_questions(findings: List[Evidence], metrics: List[Dict]) -> List[str]:
    qs = []
    categories = {f.category for f in findings}
    if "customer concentration" in categories:
        qs.append("What contractual, renewal, and relationship risks exist for the largest customers, and how portable are those relationships after a change of control?")
    if "churn / retention" in categories:
        qs.append("Provide cohort-level gross and net retention by customer segment for the last 24–36 months and explain the main drivers of churn.")
    if "litigation" in categories:
        qs.append("List all current, threatened, and recently resolved legal matters, expected exposure, insurance coverage, and management's assessment of materiality.")
    if "debt / covenant" in categories:
        qs.append("Provide all debt agreements, covenant calculations, amendment history, and any known or projected covenant pressure under the transaction case.")
    if "related-party" in categories:
        qs.append("Identify all related-party arrangements and quantify the normalized arm's-length cost or revenue impact after closing.")
    for m in metrics:
        if m.get("top_1_pct", 0) >= 20:
            qs.append(f"The largest customer represents approximately {m['top_1_pct']:.1f}% of supplied revenue. What is the renewal date, termination language, pricing history, and executive relationship ownership for this account?")
        if m.get("top_5_pct", 0) >= 50:
            qs.append(f"The top five customers represent approximately {m['top_5_pct']:.1f}% of supplied revenue. What downside case has management modeled for loss or repricing of one or more of these accounts?")
    return list(dict.fromkeys(qs))


st.title("DealLens")
st.caption("First-pass, human-supervised diligence workspace. Decision support only — not investment, legal, tax, or accounting advice.")

with st.sidebar:
    st.header("Deal workspace")
    deal_name = st.text_input("Deal name", value="Project Atlas")
    target = st.text_input("Target company", value="")
    reviewer = st.text_input("Human reviewer", value="")

uploads = st.file_uploader(
    "Upload CIM, diligence documents, customer revenue exports, or supporting files",
    type=["pdf", "txt", "md", "csv", "xlsx", "xls"],
    accept_multiple_files=True,
)

all_findings = []
all_metrics = []
processed = []

if uploads:
    for f in uploads:
        parsed = read_upload(f)
        processed.append((f.name, parsed["kind"]))
        if parsed["kind"] == "text":
            all_findings.extend(find_evidence(f.name, parsed["value"]))
        elif parsed["kind"] == "table":
            m = concentration_metrics(parsed["value"])
            if m:
                m["filename"] = f.name
                all_metrics.append(m)

    col1, col2, col3 = st.columns(3)
    col1.metric("Files processed", len(processed))
    col2.metric("Evidence flags", len(all_findings))
    col3.metric("Structured revenue files", len(all_metrics))

    st.subheader("Deterministic concentration checks")
    if all_metrics:
        for m in all_metrics:
            st.write(f"**{m['filename']}** — {m['customer_count']} customers | Top 1: {m['top_1_pct']:.1f}% | Top 5: {m['top_5_pct']:.1f}% | Supplied revenue total: ${m['total_revenue']:,.0f}")
    else:
        st.info("Upload a CSV/XLSX with columns such as Customer + Revenue (or Sales/Amount) to calculate concentration deterministically.")

    st.subheader("Source-backed evidence flags")
    if all_findings:
        for finding in all_findings:
            with st.expander(f"{finding.category.title()} — {finding.filename}"):
                st.write(finding.excerpt)
    else:
        st.info("No configured red-flag phrases were located in the extracted text. This is not evidence that the deal is free of risk.")

    st.subheader("Management diligence questions")
    questions = management_questions(all_findings, all_metrics)
    if questions:
        for i, q in enumerate(questions, 1):
            st.write(f"{i}. {q}")
    else:
        st.write("No automated questions generated yet. Add documents or structured customer-revenue data.")

    st.subheader("Reviewer gate")
    approved = st.checkbox("I reviewed the underlying evidence and deterministic calculations before using this output externally.")
    if approved and reviewer.strip():
        st.success(f"Reviewer gate completed by {reviewer.strip()} for {deal_name}.")
    elif approved:
        st.warning("Enter the human reviewer's name before treating the packet as approved.")
else:
    st.info("Upload deal materials to start the first-pass review.")

st.divider()
st.caption("MVP v0.1: local extraction + deterministic concentration metrics + evidence discovery. LLM synthesis and citation graph are intentionally gated for the next implementation step.")
