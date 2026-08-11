from __future__ import annotations

from typing import Dict
import pandas as pd


def _columns(df: pd.DataFrame) -> Dict[str, str]:
    return {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}


def customer_concentration(df: pd.DataFrame) -> Dict[str, float]:
    cols = _columns(df)
    customer_col = cols.get("customer") or cols.get("customer_name") or cols.get("name")
    revenue_col = cols.get("revenue") or cols.get("sales") or cols.get("amount")
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
        "metric_type": "customer_concentration",
        "total_revenue": total,
        "top_1_pct": float(grouped.head(1).sum() / total * 100),
        "top_5_pct": float(grouped.head(5).sum() / total * 100),
        "customer_count": int(grouped.shape[0]),
    }


def financial_statement_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate simple, auditable metrics from a row-oriented financial export.

    Supported columns: Metric/Line Item + Current/Current Year; optional Prior/Prior Year.
    Expected rows can include Revenue, EBITDA, Gross Profit, Cash, Debt, Accounts Receivable,
    Accounts Payable, Current Assets, and Current Liabilities.
    """
    cols = _columns(df)
    item_col = cols.get("metric") or cols.get("line_item") or cols.get("account") or cols.get("item")
    current_col = cols.get("current") or cols.get("current_year") or cols.get("value") or cols.get("amount")
    prior_col = cols.get("prior") or cols.get("prior_year") or cols.get("previous")
    if not item_col or not current_col:
        return {}

    w = df[[item_col, current_col] + ([prior_col] if prior_col else [])].copy()
    w[item_col] = w[item_col].astype(str).str.strip().str.lower()
    w[current_col] = pd.to_numeric(w[current_col], errors="coerce")
    if prior_col:
        w[prior_col] = pd.to_numeric(w[prior_col], errors="coerce")

    values = dict(zip(w[item_col], w[current_col]))
    prior_values = dict(zip(w[item_col], w[prior_col])) if prior_col else {}

    def val(*names):
        for n in names:
            if n in values and pd.notna(values[n]):
                return float(values[n])
        return None

    revenue = val("revenue", "net revenue", "sales")
    ebitda = val("ebitda", "adjusted ebitda")
    gross_profit = val("gross profit")
    cash = val("cash", "cash and equivalents")
    debt = val("debt", "total debt")
    current_assets = val("current assets", "total current assets")
    current_liabilities = val("current liabilities", "total current liabilities")

    result: Dict[str, float] = {"metric_type": "financial_statement"}
    if revenue is not None:
        result["revenue"] = revenue
    if ebitda is not None:
        result["ebitda"] = ebitda
        if revenue:
            result["ebitda_margin_pct"] = ebitda / revenue * 100
    if gross_profit is not None and revenue:
        result["gross_margin_pct"] = gross_profit / revenue * 100
    if cash is not None:
        result["cash"] = cash
    if debt is not None:
        result["debt"] = debt
    if cash is not None and debt is not None:
        result["net_debt"] = debt - cash
    if current_assets is not None and current_liabilities not in (None, 0):
        result["current_ratio"] = current_assets / current_liabilities

    if revenue is not None and prior_col:
        prior_revenue = None
        for name in ("revenue", "net revenue", "sales"):
            if name in prior_values and pd.notna(prior_values[name]):
                prior_revenue = float(prior_values[name])
                break
        if prior_revenue not in (None, 0):
            result["revenue_growth_pct"] = (revenue / prior_revenue - 1) * 100

    return result
