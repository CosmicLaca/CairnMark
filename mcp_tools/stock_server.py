"""Local stdio MCP server backed by the Alpha Vantage stock API."""

from __future__ import annotations

import os
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    from .http_client import RemoteServiceError, get_json
except ImportError:  # Direct execution: python mcp_tools/stock_server.py
    from http_client import RemoteServiceError, get_json


API_ENDPOINT = "https://www.alphavantage.co/query"
API_KEY_ENVIRONMENT_VARIABLE = "ALPHA_VANTAGE_API_KEY"
MCP_PASSWORD_ENVIRONMENT_VARIABLE = "MCP_SERVICE_PASSWORD"
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.^_-]{1,24}$")

mcp = FastMCP(
    "Cairnmark Stock Information",
    instructions=(
        "Search stock symbols, retrieve the latest end-of-day quote, and "
        "retrieve recent daily prices. Financial data is informational only."
    ),
)


def _api_key() -> str:
    api_key = str(
        os.environ.get(MCP_PASSWORD_ENVIRONMENT_VARIABLE)
        or os.environ.get(API_KEY_ENVIRONMENT_VARIABLE)
        or ""
    ).strip()
    if not api_key:
        raise RuntimeError(
            "An Alpha Vantage API key is required. Save it in the stock "
            "service password field."
        )
    return api_key


def _symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(normalized):
        raise ValueError(
            "symbol must contain only letters, numbers, '.', '^', '_' or '-'."
        )
    return normalized


def _request(function: str, **params: object) -> dict[str, Any]:
    payload = get_json(
        API_ENDPOINT,
        {
            "function": function,
            **params,
            "apikey": _api_key(),
        },
    )
    error = (
        payload.get("Error Message")
        or payload.get("Information")
        or payload.get("Note")
    )
    if error:
        raise RemoteServiceError(str(error))
    return payload


@mcp.tool()
def search_stock_symbols(keywords: str, limit: int = 5) -> dict[str, Any]:
    """Search for global equity, ETF, or mutual-fund ticker symbols."""
    query = keywords.strip()
    if not query:
        raise ValueError("keywords is required.")
    if not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("limit must be an integer from 1 through 10.")

    payload = _request("SYMBOL_SEARCH", keywords=query)
    raw_matches = payload.get("bestMatches")
    if not isinstance(raw_matches, list):
        raise RemoteServiceError("Alpha Vantage omitted search results.")

    matches = []
    for raw_match in raw_matches[:limit]:
        if not isinstance(raw_match, dict):
            continue
        matches.append(
            {
                "symbol": raw_match.get("1. symbol"),
                "name": raw_match.get("2. name"),
                "type": raw_match.get("3. type"),
                "region": raw_match.get("4. region"),
                "market_open": raw_match.get("5. marketOpen"),
                "market_close": raw_match.get("6. marketClose"),
                "timezone": raw_match.get("7. timezone"),
                "currency": raw_match.get("8. currency"),
                "match_score": raw_match.get("9. matchScore"),
            }
        )
    return {"query": query, "matches": matches, "source": "Alpha Vantage"}


@mcp.tool()
def get_stock_quote(symbol: str) -> dict[str, Any]:
    """Get the latest end-of-day quote available for a stock symbol."""
    normalized_symbol = _symbol(symbol)
    payload = _request("GLOBAL_QUOTE", symbol=normalized_symbol)
    quote = payload.get("Global Quote")
    if not isinstance(quote, dict) or not quote:
        raise ValueError(f"No quote was found for {normalized_symbol}.")

    return {
        "symbol": quote.get("01. symbol"),
        "open": quote.get("02. open"),
        "high": quote.get("03. high"),
        "low": quote.get("04. low"),
        "price": quote.get("05. price"),
        "volume": quote.get("06. volume"),
        "latest_trading_day": quote.get("07. latest trading day"),
        "previous_close": quote.get("08. previous close"),
        "change": quote.get("09. change"),
        "change_percent": quote.get("10. change percent"),
        "freshness": "End-of-day on the free API tier",
        "source": "Alpha Vantage",
    }


@mcp.tool()
def get_daily_stock_prices(symbol: str, days: int = 10) -> dict[str, Any]:
    """Get the most recent one-to-100 daily OHLCV rows for a stock symbol."""
    normalized_symbol = _symbol(symbol)
    if not isinstance(days, int) or not 1 <= days <= 100:
        raise ValueError("days must be an integer from 1 through 100.")

    payload = _request(
        "TIME_SERIES_DAILY",
        symbol=normalized_symbol,
        outputsize="compact",
    )
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise ValueError(f"No daily prices were found for {normalized_symbol}.")

    prices = []
    for date, raw_row in sorted(series.items(), reverse=True)[:days]:
        if not isinstance(raw_row, dict):
            continue
        prices.append(
            {
                "date": date,
                "open": raw_row.get("1. open"),
                "high": raw_row.get("2. high"),
                "low": raw_row.get("3. low"),
                "close": raw_row.get("4. close"),
                "volume": raw_row.get("5. volume"),
            }
        )
    return {
        "symbol": normalized_symbol,
        "prices": prices,
        "source": "Alpha Vantage",
    }


if __name__ == "__main__":
    _api_key()
    mcp.run(transport="stdio")
