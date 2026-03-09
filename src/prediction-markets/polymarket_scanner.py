#!/usr/bin/env python3
"""
Polymarket Arbitrage Scanner

Scans Polymarket CLOB API for arbitrage opportunities:
1. Binary markets where YES + NO < $0.98 (guaranteed profit)
2. Multi-outcome markets with mispriced complements
3. High-volume markets with recent price movements > 5%

Usage: python3 polymarket_scanner.py
"""

import json
import time
import base64
import sys
import os
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "https://clob.polymarket.com"
OUTPUT_DIR = os.path.expanduser(
    "~/cowork-brain/projects/global-arbitrage/data"
)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "polymarket_opportunities.json")
RATE_LIMIT_DELAY = 0.25  # seconds between API calls
MAX_PAGES = 40  # max pagination pages to fetch
PAGE_SIZE = 100  # markets per page
ARB_THRESHOLD = 0.98  # YES+NO below this = arb opportunity
PRICE_MOVE_THRESHOLD = 0.05  # 5% move threshold

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only fallback, tries requests first)
# ---------------------------------------------------------------------------

try:
    import requests as _requests

    def _get(url, params=None, timeout=15):
        r = _requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

except ImportError:
    def _get(url, params=None, timeout=15):
        if params:
            url = url + "?" + urlencode(params)
        req = Request(url, headers={"User-Agent": "PolymarketScanner/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())


def api_get(path, params=None):
    """Rate-limited API call."""
    time.sleep(RATE_LIMIT_DELAY)
    url = f"{BASE_URL}{path}"
    try:
        return _get(url, params=params)
    except (HTTPError, URLError, Exception) as e:
        print(f"  [WARN] API error {path}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_all_active_markets():
    """Fetch markets from CLOB API, paginating with cursor.
    Returns only markets that are accepting orders (truly active)."""
    markets = []
    cursor = None
    # Start from a high offset to skip old closed markets
    # We'll iterate from the latest pages
    cursor = base64.b64encode(b"40000").decode()

    for page in range(MAX_PAGES):
        params = {"limit": PAGE_SIZE}
        if cursor and cursor != "LTE=":
            params["next_cursor"] = cursor

        data = api_get("/markets", params=params)
        if not data or "data" not in data:
            break

        batch = data["data"]
        if not batch:
            break

        for m in batch:
            if m.get("accepting_orders") and not m.get("closed"):
                markets.append(m)

        cursor = data.get("next_cursor")
        if not cursor or cursor == "LTE=":
            break

        sys.stdout.write(
            f"\r  Fetching markets… page {page+1}, "
            f"found {len(markets)} active so far"
        )
        sys.stdout.flush()

    print(f"\r  Fetched {len(markets)} active markets from {page+1} pages.     ")
    return markets


def fetch_orderbook(token_id):
    """Fetch order book for a token."""
    data = api_get("/book", params={"token_id": token_id})
    return data


def fetch_prices(token_ids):
    """Fetch prices for multiple tokens (comma-separated IDs)."""
    if not token_ids:
        return {}
    # API accepts comma-separated token_ids
    ids_str = ",".join(token_ids)
    data = api_get("/prices", params={"token_ids": ids_str})
    return data or {}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_binary_arb(markets):
    """Find binary markets where YES + NO prices < threshold.
    In a properly-priced binary market, YES + NO should equal ~$1.00.
    If the sum is significantly less, buying both sides guarantees profit."""
    opportunities = []

    for m in markets:
        tokens = m.get("tokens", [])
        if len(tokens) != 2:
            continue

        prices = [t.get("price", 0) for t in tokens]
        # Skip markets with zero prices (no liquidity)
        if any(p == 0 for p in prices):
            continue

        total = sum(prices)
        if 0 < total < ARB_THRESHOLD:
            gap = 1.0 - total
            roi = (gap / total) * 100  # ROI if you buy both sides

            opportunities.append({
                "type": "binary_underpriced",
                "market": m["question"],
                "slug": m.get("market_slug", ""),
                "condition_id": m.get("condition_id", ""),
                "tokens": [
                    {
                        "outcome": t["outcome"],
                        "price": t["price"],
                        "token_id": t["token_id"],
                    }
                    for t in tokens
                ],
                "total_price": round(total, 4),
                "gap": round(gap, 4),
                "roi_pct": round(roi, 2),
                "explanation": (
                    f"Buy both outcomes for ${total:.4f}, "
                    f"guaranteed payout $1.00. "
                    f"Profit: ${gap:.4f} ({roi:.2f}% ROI)"
                ),
            })

    opportunities.sort(key=lambda x: x["roi_pct"], reverse=True)
    return opportunities


def analyze_overpriced_markets(markets):
    """Find binary markets where YES + NO prices > $1.02.
    This means selling both sides (if possible) locks in profit."""
    opportunities = []

    for m in markets:
        tokens = m.get("tokens", [])
        if len(tokens) != 2:
            continue

        prices = [t.get("price", 0) for t in tokens]
        if any(p == 0 for p in prices):
            continue

        total = sum(prices)
        if total > 1.02:
            excess = total - 1.0
            roi = (excess / 1.0) * 100

            opportunities.append({
                "type": "binary_overpriced",
                "market": m["question"],
                "slug": m.get("market_slug", ""),
                "condition_id": m.get("condition_id", ""),
                "tokens": [
                    {
                        "outcome": t["outcome"],
                        "price": t["price"],
                        "token_id": t["token_id"],
                    }
                    for t in tokens
                ],
                "total_price": round(total, 4),
                "excess": round(excess, 4),
                "roi_pct": round(roi, 2),
                "explanation": (
                    f"Sum of outcomes = ${total:.4f} > $1.00. "
                    f"Selling both sides profits ${excess:.4f} ({roi:.2f}% ROI)"
                ),
            })

    opportunities.sort(key=lambda x: x["roi_pct"], reverse=True)
    return opportunities


def analyze_neg_risk_arb(markets):
    """Find neg-risk (multi-outcome) markets where sum of all outcome
    prices is significantly different from $1.00."""
    # Group markets by neg_risk_market_id
    groups = {}
    for m in markets:
        nrm_id = m.get("neg_risk_market_id", "")
        if not nrm_id or not m.get("neg_risk"):
            continue
        groups.setdefault(nrm_id, []).append(m)

    opportunities = []
    for nrm_id, group in groups.items():
        # Each market in a neg-risk group has a YES token
        # The YES prices across all markets in the group should sum to ~1.0
        yes_prices = []
        market_info = []
        for m in group:
            tokens = m.get("tokens", [])
            for t in tokens:
                if t.get("outcome", "").lower() in ("yes", "") or len(tokens) == 2:
                    # First token is typically YES
                    price = t.get("price", 0)
                    if price > 0:
                        yes_prices.append(price)
                        market_info.append({
                            "question": m["question"],
                            "outcome": t.get("outcome", "YES"),
                            "price": price,
                            "token_id": t["token_id"],
                        })
                    break

        if len(yes_prices) < 2:
            continue

        total = sum(yes_prices)
        if total < ARB_THRESHOLD:
            gap = 1.0 - total
            roi = (gap / total) * 100
            opportunities.append({
                "type": "neg_risk_underpriced",
                "neg_risk_market_id": nrm_id,
                "num_outcomes": len(yes_prices),
                "markets": market_info,
                "total_price": round(total, 4),
                "gap": round(gap, 4),
                "roi_pct": round(roi, 2),
                "explanation": (
                    f"{len(yes_prices)}-outcome group sums to ${total:.4f}. "
                    f"Buy all YES tokens for guaranteed ${gap:.4f} profit "
                    f"({roi:.2f}% ROI)"
                ),
            })
        elif total > 1.02:
            excess = total - 1.0
            roi = (excess / 1.0) * 100
            opportunities.append({
                "type": "neg_risk_overpriced",
                "neg_risk_market_id": nrm_id,
                "num_outcomes": len(yes_prices),
                "markets": market_info,
                "total_price": round(total, 4),
                "excess": round(excess, 4),
                "roi_pct": round(roi, 2),
                "explanation": (
                    f"{len(yes_prices)}-outcome group sums to ${total:.4f}. "
                    f"Overpriced by ${excess:.4f} ({roi:.2f}% ROI if selling)"
                ),
            })

    opportunities.sort(key=lambda x: x["roi_pct"], reverse=True)
    return opportunities


def analyze_price_movements(markets):
    """Identify markets with significant price skew that may indicate
    recent movement. Since the CLOB API doesn't provide historical prices,
    we flag markets where one side is priced between 0.45-0.55 (competitive)
    and the spread between mid-price and 0.50 exceeds the threshold."""
    movers = []

    for m in markets:
        tokens = m.get("tokens", [])
        if len(tokens) != 2:
            continue

        prices = [t.get("price", 0) for t in tokens]
        if any(p == 0 for p in prices):
            continue

        # Check order book for spread if available
        # For now, flag competitive markets with unusual pricing
        total = sum(prices)
        if total == 0:
            continue

        # Normalized prices
        p1 = prices[0] / total if total > 0 else 0.5
        deviation = abs(p1 - 0.5)

        # Markets close to 50/50 but with slight edge are interesting
        # Only check markets that have orderbook enabled
        if (0.05 < prices[0] < 0.95 and 0.05 < prices[1] < 0.95
                and m.get("enable_order_book")):
            # Check for orderbook depth
            token_id = tokens[0]["token_id"]
            book = fetch_orderbook(token_id)

            if book and "bids" in book and "asks" in book:
                bids = book.get("bids", [])
                asks = book.get("asks", [])

                if bids and asks:
                    best_bid = float(bids[0].get("price", 0))
                    best_ask = float(asks[0].get("price", 1))
                    spread = best_ask - best_bid
                    spread_pct = spread / best_ask * 100 if best_ask > 0 else 0

                    # Wide spread = potential opportunity
                    if spread_pct > PRICE_MOVE_THRESHOLD * 100:
                        bid_depth = sum(
                            float(b.get("size", 0)) for b in bids[:5]
                        )
                        ask_depth = sum(
                            float(a.get("size", 0)) for a in asks[:5]
                        )

                        movers.append({
                            "type": "wide_spread",
                            "market": m["question"],
                            "slug": m.get("market_slug", ""),
                            "condition_id": m.get("condition_id", ""),
                            "tokens": [
                                {
                                    "outcome": t["outcome"],
                                    "price": t["price"],
                                    "token_id": t["token_id"],
                                }
                                for t in tokens
                            ],
                            "best_bid": best_bid,
                            "best_ask": best_ask,
                            "spread": round(spread, 4),
                            "spread_pct": round(spread_pct, 2),
                            "bid_depth_5": round(bid_depth, 2),
                            "ask_depth_5": round(ask_depth, 2),
                            "explanation": (
                                f"Spread: ${spread:.4f} ({spread_pct:.1f}%). "
                                f"Bid depth: {bid_depth:.0f}, "
                                f"Ask depth: {ask_depth:.0f}"
                            ),
                        })

            # Rate limit orderbook calls - only check a sample
            if len(movers) >= 20:
                break

    movers.sort(key=lambda x: x["spread_pct"], reverse=True)
    return movers


def find_correlated_markets(markets):
    """Find potentially correlated markets by keyword matching.
    Markets about the same topic/entity may have exploitable price
    discrepancies."""
    # Build keyword index
    from collections import defaultdict

    keyword_markets = defaultdict(list)
    important_keywords = set()

    for m in markets:
        question = m.get("question", "").lower()
        tokens = m.get("tokens", [])
        if len(tokens) != 2:
            continue

        prices = [t.get("price", 0) for t in tokens]
        if any(p == 0 for p in prices):
            continue

        # Extract meaningful words (>4 chars, not common words)
        stop_words = {
            "will", "the", "this", "that", "with", "from", "have",
            "been", "more", "than", "before", "after", "during",
            "about", "above", "below", "under", "over", "between",
        }
        words = set()
        for w in question.split():
            w = w.strip("?.,!\"'()[]{}").lower()
            if len(w) > 4 and w not in stop_words:
                words.add(w)

        for w in words:
            keyword_markets[w].append({
                "question": m["question"],
                "slug": m.get("market_slug", ""),
                "yes_price": prices[0],
                "no_price": prices[1],
                "condition_id": m.get("condition_id", ""),
            })

    # Find keywords with multiple markets
    correlations = []
    seen_pairs = set()

    for keyword, mlist in keyword_markets.items():
        if len(mlist) < 2 or len(mlist) > 10:
            continue

        # Compare all pairs
        for i in range(len(mlist)):
            for j in range(i + 1, len(mlist)):
                m1, m2 = mlist[i], mlist[j]
                pair_key = tuple(sorted([m1["condition_id"], m2["condition_id"]]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Price discrepancy
                diff = abs(m1["yes_price"] - m2["yes_price"])
                if diff > PRICE_MOVE_THRESHOLD:
                    correlations.append({
                        "type": "correlated_discrepancy",
                        "keyword": keyword,
                        "market_a": {
                            "question": m1["question"],
                            "slug": m1["slug"],
                            "yes_price": m1["yes_price"],
                        },
                        "market_b": {
                            "question": m2["question"],
                            "slug": m2["slug"],
                            "yes_price": m2["yes_price"],
                        },
                        "price_diff": round(diff, 4),
                        "explanation": (
                            f"Related markets (keyword: '{keyword}') "
                            f"with {diff:.1%} price difference. "
                            f"A: {m1['yes_price']:.2f} vs B: {m2['yes_price']:.2f}"
                        ),
                    })

    correlations.sort(key=lambda x: x["price_diff"], reverse=True)
    return correlations[:30]  # Top 30


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_summary(results):
    """Print human-readable summary."""
    print("\n" + "=" * 70)
    print("  POLYMARKET ARBITRAGE SCANNER RESULTS")
    print(f"  Scan time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    total_opps = sum(len(v) for v in results.values() if isinstance(v, list))
    print(f"\n  Total opportunities found: {total_opps}")

    # Binary underpriced
    section = results.get("binary_underpriced", [])
    print(f"\n{'─' * 70}")
    print(f"  BINARY UNDERPRICED (YES + NO < ${ARB_THRESHOLD}): {len(section)} found")
    print(f"{'─' * 70}")
    if section:
        for i, opp in enumerate(section[:10], 1):
            print(f"\n  {i}. {opp['market']}")
            for t in opp["tokens"]:
                print(f"     {t['outcome']}: ${t['price']:.4f}")
            print(f"     Total: ${opp['total_price']:.4f}  |  "
                  f"Gap: ${opp['gap']:.4f}  |  ROI: {opp['roi_pct']:.2f}%")
    else:
        print("  (none found)")

    # Binary overpriced
    section = results.get("binary_overpriced", [])
    print(f"\n{'─' * 70}")
    print(f"  BINARY OVERPRICED (YES + NO > $1.02): {len(section)} found")
    print(f"{'─' * 70}")
    if section:
        for i, opp in enumerate(section[:10], 1):
            print(f"\n  {i}. {opp['market']}")
            for t in opp["tokens"]:
                print(f"     {t['outcome']}: ${t['price']:.4f}")
            print(f"     Total: ${opp['total_price']:.4f}  |  "
                  f"Excess: ${opp['excess']:.4f}  |  ROI: {opp['roi_pct']:.2f}%")
    else:
        print("  (none found)")

    # Neg-risk groups
    for section_key in ("neg_risk_underpriced", "neg_risk_overpriced"):
        section = results.get(section_key, [])
        label = section_key.replace("_", " ").upper()
        print(f"\n{'─' * 70}")
        print(f"  {label}: {len(section)} found")
        print(f"{'─' * 70}")
        if section:
            for i, opp in enumerate(section[:10], 1):
                print(f"\n  {i}. {opp['num_outcomes']}-outcome group "
                      f"(neg_risk_id: {opp['neg_risk_market_id'][:16]}…)")
                for mk in opp["markets"][:5]:
                    print(f"     {mk['outcome']}: ${mk['price']:.4f} "
                          f"— {mk['question'][:60]}")
                if len(opp["markets"]) > 5:
                    print(f"     ... and {len(opp['markets']) - 5} more")
                print(f"     Sum: ${opp['total_price']:.4f}  |  "
                      f"ROI: {opp['roi_pct']:.2f}%")
        else:
            print("  (none found)")

    # Wide spreads
    section = results.get("wide_spreads", [])
    print(f"\n{'─' * 70}")
    print(f"  WIDE SPREAD OPPORTUNITIES: {len(section)} found")
    print(f"{'─' * 70}")
    if section:
        for i, opp in enumerate(section[:10], 1):
            print(f"\n  {i}. {opp['market']}")
            print(f"     Bid: ${opp['best_bid']:.4f}  |  "
                  f"Ask: ${opp['best_ask']:.4f}  |  "
                  f"Spread: {opp['spread_pct']:.1f}%")
            print(f"     Depth (5 levels): "
                  f"Bid {opp['bid_depth_5']:.0f} / "
                  f"Ask {opp['ask_depth_5']:.0f}")
    else:
        print("  (none found — orderbook data may be unavailable)")

    # Correlated
    section = results.get("correlated", [])
    print(f"\n{'─' * 70}")
    print(f"  CORRELATED MARKET DISCREPANCIES: {len(section)} found")
    print(f"{'─' * 70}")
    if section:
        for i, opp in enumerate(section[:10], 1):
            print(f"\n  {i}. Keyword: '{opp['keyword']}'  "
                  f"(diff: {opp['price_diff']:.1%})")
            print(f"     A: ${opp['market_a']['yes_price']:.2f} — "
                  f"{opp['market_a']['question'][:55]}")
            print(f"     B: ${opp['market_b']['yes_price']:.2f} — "
                  f"{opp['market_b']['question'][:55]}")
    else:
        print("  (none found)")

    print(f"\n{'=' * 70}")
    print(f"  Results saved to: {OUTPUT_FILE}")
    print(f"{'=' * 70}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Polymarket Arbitrage Scanner")
    print(f"Scanning at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}…\n")

    # 1. Fetch markets
    print("[1/5] Fetching active markets…")
    markets = fetch_all_active_markets()

    if not markets:
        print("No active markets found. Exiting.")
        sys.exit(1)

    print(f"  Active markets: {len(markets)}")

    # 2. Binary arb analysis
    print("[2/5] Scanning for binary arbitrage (underpriced)…")
    binary_under = analyze_binary_arb(markets)
    print(f"  Found {len(binary_under)} underpriced opportunities")

    # 3. Binary overpriced
    print("[3/5] Scanning for binary arbitrage (overpriced)…")
    binary_over = analyze_overpriced_markets(markets)
    print(f"  Found {len(binary_over)} overpriced opportunities")

    # 4. Neg-risk group analysis
    print("[4/5] Scanning neg-risk (multi-outcome) markets…")
    neg_risk = analyze_neg_risk_arb(markets)
    neg_under = [o for o in neg_risk if o["type"] == "neg_risk_underpriced"]
    neg_over = [o for o in neg_risk if o["type"] == "neg_risk_overpriced"]
    print(f"  Found {len(neg_under)} underpriced, {len(neg_over)} overpriced groups")

    # 5. Price movements / wide spreads (samples orderbooks)
    print("[5/5] Checking orderbook spreads (sampling)…")
    # Only check a subset to avoid too many API calls
    sample = [m for m in markets if len(m.get("tokens", [])) == 2
              and m.get("enable_order_book")
              and all(t.get("price", 0) > 0 for t in m["tokens"])][:30]
    wide_spreads = analyze_price_movements(sample)
    print(f"  Found {len(wide_spreads)} wide-spread opportunities")

    # 6. Correlated markets
    print("[bonus] Finding correlated market discrepancies…")
    correlated = find_correlated_markets(markets)
    print(f"  Found {len(correlated)} correlated discrepancies")

    # Compile results
    results = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "total_active_markets": len(markets),
        "binary_underpriced": binary_under,
        "binary_overpriced": binary_over,
        "neg_risk_underpriced": neg_under,
        "neg_risk_overpriced": neg_over,
        "wide_spreads": wide_spreads,
        "correlated": correlated,
        "summary": {
            "total_opportunities": (
                len(binary_under) + len(binary_over) +
                len(neg_under) + len(neg_over) +
                len(wide_spreads) + len(correlated)
            ),
            "best_binary_roi": (
                binary_under[0]["roi_pct"] if binary_under else 0
            ),
            "best_neg_risk_roi": (
                neg_under[0]["roi_pct"] if neg_under else 0
            ),
        },
    }

    # Save JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print_summary(results)


if __name__ == "__main__":
    main()
