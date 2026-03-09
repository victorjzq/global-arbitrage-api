# 🌍 Global Arbitrage Engine

**AI-powered system that finds price gaps across global markets and converts them into money — 24/7, fully automated.**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/victorjzq/global-arbitrage-api)

> *"Human civilization's wealth is already there. Just go pick it up."*

## What This Does

Scans price differences between markets worldwide and generates actionable intelligence — automatically, every 6 hours.

**Real findings (March 2026):**

| Product | China (1688) | Vietnam (Shopee) | Markup |
|---------|-------------|------------------|--------|
| Kids STEM Robot | ¥45 ($6) | 550k VND ($22) | **3.5x** |
| Pet GPS Tracker | ¥38 ($5) | 450k VND ($18) | **3.4x** |
| Foldable Keyboard | ¥28 ($4) | 320k VND ($13) | **3.3x** |
| Solar WiFi Camera | ¥75 ($10) | 850k VND ($34) | **3.2x** |

**26 categories** across **9 trade routes** (CN→VN, CN→TH, CN→ID, JP→SEA, KR→SEA).

## The Model: Token → Money

```
Energy → Tokens → AI Model → Information Gaps → Money
         ↑                                        │
         └────────── reinvest ────────────────────┘
```

Three principles:
1. **Token business** — AI tokens are raw material. Different models = different conversion efficiency.
2. **Information arbitrage** — Money comes from asymmetric information: price gaps, trend gaps, language barriers.
3. **Exponential growth** — Tools that build tools. Each scan makes the system smarter.

## Architecture

```
Scanners (3)          Engine              Output
┌──────────────┐     ┌──────────┐     ┌──────────────┐
│ Trend Gap    │────▶│ Perpetual│────▶│ API (24/7)   │
│ Price Scan   │     │ Engine   │     │ Reports      │
│ Polymarket   │     │ (6h cycle)│    │ Content (5x) │
└──────────────┘     └────┬─────┘     │ Telegram Bot │
                          │           └──────────────┘
                    ┌─────▼─────┐
                    │ Evolution │  ← self-optimization
                    │ Loop      │    from own data
                    └───────────┘
```

## Quick Start

```bash
git clone https://github.com/victorjzq/global-arbitrage-api.git
cd global-arbitrage-api
pip3 install requests pytrends

# Run full scan + content generation + self-optimization
python3 src/perpetual_engine.py

# Start API
python3 src/api_server.py
# → http://localhost:8899/api/top

# Deploy 24/7 (PM2 + cron)
bash start.sh

# Check status
python3 src/system_status.py
```

## 12 Engines

| Engine | What it does |
|--------|-------------|
| `trend_gap_scanner` | Finds products hot in China but not yet in SEA |
| `daily_scan` | Price comparison across platforms |
| `polymarket_scanner` | Prediction market arbitrage (2000+ markets) |
| `arbitrage_api` | REST API — 26 categories, 9 routes |
| `content_engine` | 1 data point → Twitter + LinkedIn + Reddit + Email + Video |
| `opportunity_ranker` | Scores by ROI × confidence × urgency |
| `evolution_loop` | Self-optimization — learns from own output |
| `perpetual_engine` | Orchestrator — runs every 6h automatically |
| `publish_report` | Multi-channel distribution |
| `telegram_bot` | Subscription alerts (Stripe + crypto payments) |
| `system_status` | One-command dashboard |
| `md_to_html` | Reports → sellable HTML/PDF |

## API Endpoints

```bash
GET /api/top              # Top opportunities (high profit)
GET /api/search?q=beauty  # Search by keyword
GET /api/routes           # All trade routes
GET /api/stats            # Usage statistics
```

## Why This Exists

Most people think arbitrage requires capital. It doesn't — it requires **information**.

- A product on 1688 for ¥45 sells on Shopee VN for $22. The gap exists because of **language barriers** (1688 is Chinese-only), **payment barriers** (needs Alipay), and **discovery barriers** (Vietnamese sellers can't search 1688).
- A trend on Douyin (Chinese TikTok) takes 5-8 months to reach Vietnam. That's a **time window** for first movers.
- Polymarket prices diverge from reality when news breaks in one language first. That's a **speed gap**.

AI eliminates all three barriers. This system does it automatically.

## Monetization (built into the system)

| Channel | Status | Revenue Model |
|---------|--------|--------------|
| Reports (Gumroad/Substack) | ✅ Live | $9-29/report |
| Telegram Bot | ✅ Code ready | $29/mo subscription |
| API (RapidAPI) | ✅ Ready to deploy | Per-request pricing |
| Freelancing (Fiverr) | ✅ Gig copy ready | $30-120/gig |
| Content (5 platforms) | ✅ Auto-generating | Ad revenue + leads |

## Self-Hosted Deploy

```bash
# PM2 (recommended)
bash start.sh

# Docker
docker build -t arbitrage . && docker run -p 8899:8899 arbitrage

# Render.com — click the button at top ↑
```

## Contributing

The system is designed to be extended:
- Add new scanners (new countries, new platforms)
- Add new trade routes (Africa, Latin America, Middle East)
- Improve the evolution algorithm
- Add new content templates
- Build new monetization adapters

## License

MIT — Use it, fork it, make money with it.

---

**Built by an AI that was told: "Money is right there. Go pick it up."**

🤖 **Telegram Bot:** [@victorjiabot](https://t.me/victorjiabot) — Free daily opportunities
📊 **Live Report:** [Substack](https://victorjia.substack.com/p/cross-border-e-commerce-arbitrage)
📝 **Dev.to:** [How I Built It](https://dev.to/victorjia/i-built-an-ai-that-finds-3-5x-price-gaps-between-china-and-southeast-asia-heres-the-data-15on)
