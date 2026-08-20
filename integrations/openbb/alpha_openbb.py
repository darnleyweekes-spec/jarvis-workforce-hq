#!/usr/bin/env python3
"""Read-only OpenBB adapter for ALPHA Mission Control."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from openbb import obb


@dataclass
class AlphaFinanceResult:
    capability: str
    read_only: bool
    query: dict[str, Any]
    data: Any
    warnings: list[str]


def _normalize(result: Any) -> Any:
    """Convert OpenBB results into JSON-safe data without provider internals."""
    if hasattr(result, "to_df"):
        frame = result.to_df()
        return frame.reset_index().to_dict(orient="records")
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, (list, dict, str, int, float, bool)) or result is None:
        return result
    return str(result)


def quote(symbol: str) -> AlphaFinanceResult:
    symbol = symbol.strip().upper()
    result = obb.equity.price.quote(symbol=symbol)
    return AlphaFinanceResult(
        capability="openbb_finance",
        read_only=True,
        query={"operation": "quote", "symbol": symbol},
        data=_normalize(result),
        warnings=["Market data may be delayed depending on the active OpenBB provider."],
    )


def history(symbol: str, start_date: str | None = None, end_date: str | None = None) -> AlphaFinanceResult:
    symbol = symbol.strip().upper()
    kwargs: dict[str, Any] = {"symbol": symbol}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    result = obb.equity.price.historical(**kwargs)
    return AlphaFinanceResult(
        capability="openbb_finance",
        read_only=True,
        query={"operation": "history", **kwargs},
        data=_normalize(result),
        warnings=["Historical coverage varies by provider."],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ALPHA read-only OpenBB finance adapter")
    sub = parser.add_subparsers(dest="command", required=True)

    quote_parser = sub.add_parser("quote", help="Fetch an equity quote")
    quote_parser.add_argument("symbol")

    history_parser = sub.add_parser("history", help="Fetch historical equity prices")
    history_parser.add_argument("symbol")
    history_parser.add_argument("--start-date")
    history_parser.add_argument("--end-date")

    args = parser.parse_args()
    if args.command == "quote":
        output = quote(args.symbol)
    else:
        output = history(args.symbol, args.start_date, args.end_date)

    print(json.dumps(asdict(output), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
