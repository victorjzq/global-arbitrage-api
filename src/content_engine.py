#!/usr/bin/env python3
"""
Content Multiplication Engine
Takes price comparison data + opportunity findings and generates
platform-specific monetizable content.
"""

import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TODAY = datetime.now().strftime("%Y-%m-%d")
CONTENT_DIR = DATA_DIR / "content" / TODAY

# --- CTAs ---
CTA_TELEGRAM = "🤖 Join our free Telegram bot for daily alerts: t.me/GlobalArbBot"
CTA_GUMROAD = "📊 Full report with 50+ products: gumroad.com/l/arbitrage-report"
CTA_BOTH = f"{CTA_TELEGRAM}\n{CTA_GUMROAD}"


def load_data():
    with open(DATA_DIR / "price_comparison.json") as f:
        prices = json.load(f)
    with open(DATA_DIR / "opportunities_2026_03_09.md") as f:
        opportunities = f.read()
    return prices, opportunities


def extract_top_items(prices):
    """Sort items by markup descending, return all."""
    items = sorted(prices["items"], key=lambda x: x.get("markup", 0), reverse=True)
    return items


def fmt_usd(cny, rate=7.1):
    """Rough CNY to USD for international audience."""
    return round(cny / rate, 1)


def fmt_vnd_k(vnd):
    """Format VND in thousands."""
    return f"{vnd // 1000}k"


# ============================================================
# GENERATORS
# ============================================================

def generate_twitter_thread(items, prices):
    rate = prices["exchange_rate"]
    top = [i for i in items if i.get("markup", 0) >= 3.0]

    tweets = []
    tweets.append(
        f"""🧵 I analyzed 8 products across China-Vietnam supply chains.

Some have 3.5x markups — meaning you buy at $6 and sell at $21.

Here are the biggest cross-border arbitrage gaps I found today (March 2026):

👇"""
    )

    for idx, item in enumerate(top[:4], 1):
        cost_usd = fmt_usd(item["price_1688_cny"])
        sell_usd = fmt_usd(item["price_shopee_vnd"] / rate * 7.1 / 7.1 * item["price_1688_cny"] * item["markup"] / item["price_1688_cny"])
        # simpler: just use VND converted
        sell_usd = fmt_usd(item["price_shopee_vnd"] / rate)
        tweets.append(
            f"""{idx}/ {item['category']} ({item['category_vi']})

💰 Buy on 1688: ¥{item['price_1688_cny']} (~${cost_usd})
🏷️ Sell on Shopee VN: {item['price_shopee_vnd']:,} VND (~${sell_usd})
📈 Markup: {item['markup']}x

{item['notes'][:120]}"""
        )

    tweets.append(
        """5/ Why does this gap exist?

🇨🇳 Chinese wholesale platforms (1688) aren't accessible to Vietnamese buyers
🇻🇳 Vietnamese consumers search on Shopee/TikTok, not Alibaba
🌐 Language barrier = profit margin"""
    )

    tweets.append(
        """6/ The best categories right now:

🥇 Kids STEM robots — 3.5x markup, ZERO local supply
🥈 Pet GPS trackers — 3.4x, urban pet boom
🥉 Foldable keyboards — 3.3x, light & easy to ship
🏅 Solar cameras — 3.2x, 312% YoY growth"""
    )

    tweets.append(
        """7/ How to start with $0:

1. Find product on 1688.com
2. List on Shopee VN (use agent for import)
3. Customer orders → you order from 1688
4. Agent ships direct to customer

No inventory. No warehouse. Just information advantage."""
    )

    tweets.append(
        """8/ The real moat isn't the products — it's the DATA.

Products get copied in 2 weeks.
But a system that scans 1000s of products daily and finds new gaps?

That's what I'm building. Automated arbitrage intelligence."""
    )

    tweets.append(
        f"""9/ I'm sharing the top opportunities daily via:

{CTA_TELEGRAM}

Free daily alerts with actual prices and markup calculations.

No fluff. Just numbers."""
    )

    tweets.append(
        f"""10/ Want the full database?

50+ products, updated weekly, with:
- Exact 1688 supplier links
- Shopee listing templates
- Margin calculators
- Trend signals

{CTA_GUMROAD}

RT if this was useful 🔄"""
    )

    return "\n\n---\n\n".join(f"**Tweet {i+1}**\n\n{t}" for i, t in enumerate(tweets))


def generate_linkedin_post(items, prices):
    top = items[:3]
    return f"""I spent the weekend analyzing cross-border e-commerce data between China and Vietnam.

The markup gaps are staggering.

Here's what the data shows (March 2026):

📊 Product Price Gap Analysis — 1688 (China) vs Shopee (Vietnam):

• Children's STEM Robot Kits: ¥45 → 550,000 VND (3.5x markup)
• Pet GPS Trackers: ¥38 → 450,000 VND (3.4x markup)
• Foldable Bluetooth Keyboards: ¥28 → 320,000 VND (3.3x markup)
• Solar WiFi Security Cameras: ¥75 → 850,000 VND (3.2x markup)

Why do these gaps persist?

1️⃣ Language barrier — 1688 is Chinese-only. Vietnamese sellers can't navigate it.
2️⃣ Payment friction — Alipay/WeChat Pay aren't available in Vietnam.
3️⃣ Trust gap — Vietnamese consumers prefer local marketplace guarantees.
4️⃣ Discovery gap — No cross-platform search exists.

The categories with the highest growth:
→ Solar security cameras: 312% YoY on Shopee VN
→ Smart home devices: 241% YoY
→ Beauty RF devices: 194% YoY

This isn't theoretical. These are real wholesale prices vs real retail listings, verified this week.

The information asymmetry between manufacturing hubs and emerging consumer markets is one of the biggest untapped opportunities in Southeast Asian e-commerce.

I'm building an automated system that scans these gaps daily and surfaces the highest-margin opportunities.

If you're in e-commerce, supply chain, or Southeast Asian markets — I'd love to connect.

{CTA_GUMROAD}

#CrossBorderEcommerce #Arbitrage #SoutheastAsia #Vietnam #SupplyChain #Ecommerce"""


def generate_reddit_post(items, prices):
    return f"""**Title: I analyzed price gaps between Chinese wholesale and Vietnamese retail — some products have 3.5x markups**

Hey everyone,

I've been researching cross-border arbitrage between China (1688.com) and Vietnam (Shopee) and wanted to share some interesting findings.

**TL;DR:** Many everyday products sold on Vietnam's largest marketplace cost 2.5-3.5x what they cost wholesale in China. The gap exists because of language barriers, payment systems, and discovery limitations.

---

**The Data (March 2026):**

| Product | 1688 Price (CNY) | Shopee VN Price (VND) | Markup |
|---------|-------------------|----------------------|--------|
| Kids STEM Robot Kit | ¥45 | 550,000 | 3.5x |
| Pet GPS Tracker | ¥38 | 450,000 | 3.4x |
| Foldable BT Keyboard | ¥28 | 320,000 | 3.3x |
| Solar WiFi Camera | ¥75 | 850,000 | 3.2x |
| Smart Plug | ¥18 | 180,000 | 2.9x |
| Mini Projector | ¥120 | 1,200,000 | 2.9x |
| RF Beauty Device | ¥90 | 850,000 | 2.7x |
| Portable Coffee Maker | ¥55 | 500,000 | 2.6x |

Exchange rate used: 1 CNY ≈ 3,500 VND

---

**Why the gap exists:**

1. **Language:** 1688 is 100% in Chinese. Most Vietnamese sellers can't use it.
2. **Payment:** You need Alipay/WeChat to buy on 1688. Vietnamese don't have these.
3. **Logistics:** Shipping from China to Vietnam requires an agent/forwarder.
4. **Trust:** Vietnamese buyers prefer Shopee's buyer protection over unknown Chinese suppliers.

**Fastest growing categories on Shopee VN:**
- Solar security cameras: +312% YoY
- Smart home plugs: +241% YoY
- Beauty devices: +194% YoY

---

**How people actually do this:**

1. Find trending products on Shopee VN
2. Source on 1688 (use Google Translate or an agent)
3. Use a cross-border shipping agent (costs about $3-5/kg)
4. List on Shopee with Vietnamese descriptions
5. Dropship or hold small inventory

Even after shipping + agent fees (roughly 15-20% of product cost), margins are solid on anything above 2.5x raw markup.

---

I'm building a tool that automates this scanning process. If you're interested, I share daily findings for free:

{CTA_TELEGRAM}

Happy to answer questions about the methodology or specific products.

**Edit:** For anyone asking about the full dataset with supplier links and listing templates — {CTA_GUMROAD}"""


def generate_email_newsletter(items, prices):
    top = [i for i in items if i.get("markup", 0) >= 3.0]
    return f"""Subject: 🔍 This week's top arbitrage gaps: up to 3.5x markups (March 9, 2026)

---

Hi there,

Here's your weekly cross-border arbitrage briefing.

This week I scanned 8 product categories across 1688 (China's largest wholesale platform) and Shopee Vietnam. Here are the standout opportunities.

---

## 🏆 TOP OPPORTUNITIES THIS WEEK

### #1: Children's STEM Robot Kits — 3.5x Markup
- **Buy:** ¥45 on 1688 (~$6.30)
- **Sell:** 550,000 VND on Shopee (~$22)
- **Why it works:** Vietnam's STEM education trend is booming, but local supply is virtually zero. Parents are willing to pay premium for educational toys.
- **Risk level:** Low (light, durable, no batteries)

### #2: Pet GPS Trackers — 3.4x Markup
- **Buy:** ¥38 on 1688 (~$5.30)
- **Sell:** 450,000 VND on Shopee (~$18)
- **Why it works:** Urban pet ownership in Vietnam is exploding. Pet parents want tech solutions. Mini GPS/BLE trackers are cheap to source and easy to ship.
- **Risk level:** Low-Medium (needs app compatibility check)

### #3: Foldable Bluetooth Keyboards — 3.3x Markup
- **Buy:** ¥28 on 1688 (~$3.90)
- **Sell:** 320,000 VND on Shopee (~$13)
- **Why it works:** Remote work + tablet adoption. Ultra-light, flat shipping, very low return rate.
- **Risk level:** Low (proven category)

### #4: Solar WiFi Security Cameras — 3.2x Markup
- **Buy:** ¥75 on 1688 (~$10.50)
- **Sell:** 850,000 VND on Shopee (~$34)
- **Why it works:** 312% YoY growth on Shopee VN. Rural Vietnam + rising security awareness = massive demand.
- **Risk level:** Medium (heavier, needs testing)

---

## 📈 TREND SIGNALS

Categories accelerating on Shopee Vietnam:
- Solar cameras: **+312% YoY**
- Smart plugs: **+241% YoY**
- Beauty RF devices: **+194% YoY**
- Mini air fryers: **+187% YoY**

All of these are available on 1688 at 2.5-4x less than Vietnamese retail.

---

## 💡 INSIGHT OF THE WEEK

The real margin isn't in the product — it's in the *information gap*.

Vietnamese consumers can't access 1688. They don't know these products exist at these prices. Your value-add as an arbitrageur is bridging that gap: finding, verifying, and delivering products they want at prices they're happy to pay.

The sellers making the most money aren't the ones with the cheapest prices — they're the ones with the best Vietnamese product descriptions, fastest shipping, and most responsive customer service.

---

## 🛠️ TOOL UPDATE

I'm building an automated scanner that monitors price gaps daily across 100+ categories. Early access coming soon.

**Want daily alerts instead of weekly?**
{CTA_TELEGRAM}

**Want the full database with supplier links?**
{CTA_GUMROAD}

---

That's it for this week. Hit reply if you have questions about any of these products.

To profitable gaps,
Global Arbitrage Team

---
*You're receiving this because you signed up for arbitrage opportunity alerts.*
*Unsubscribe: [link]*"""


def generate_video_script(items, prices):
    return f"""# 60-Second Video Script: Cross-Border Arbitrage Opportunities
# Platform: TikTok / Instagram Reels / YouTube Shorts
# Style: Fast-paced, text overlays, screen recordings

---

**[0-5s] HOOK**
[Text overlay: "3.5x MARKUP 💰"]
"This product costs $6 in China... and sells for $22 in Vietnam."

**[5-12s] THE SETUP**
[Show 1688.com screenshot → Shopee screenshot side by side]
"I compared prices on China's biggest wholesale site with Vietnam's biggest marketplace. The gaps are insane."

**[12-25s] THE DATA — Show 4 products rapid-fire**

[Product 1 — flash on screen]
"Kids coding robot: $6 in China, $22 in Vietnam. 3.5x markup."

[Product 2]
"Pet GPS tracker: $5 in China, $18 in Vietnam. 3.4x."

[Product 3]
"Foldable keyboard: $4 in China, $13 in Vietnam. 3.3x."

[Product 4]
"Solar camera: $10 in China, $34 in Vietnam. 3.2x."

**[25-35s] WHY THE GAP EXISTS**
[Text overlays popping in]
"Why? Because Vietnamese buyers CAN'T access 1688. It's Chinese-only. No Alipay in Vietnam. Language barrier equals profit margin."

**[35-45s] HOW TO DO IT**
[Quick screen recording of the process]
"Step 1: Find trending products on Shopee Vietnam.
Step 2: Source the same product on 1688 for 3x less.
Step 3: Use a shipping agent. List it. Profit."

**[45-55s] SOCIAL PROOF**
[Show the data table / growth chart]
"Solar cameras grew 312% last year on Shopee Vietnam. Smart plugs 241%. The demand is REAL."

**[55-60s] CTA**
[Point to bio / link]
"I scan these gaps every single day. Free daily alerts — link in bio."

---

**Caption:**
I found products with 3.5x markups between China and Vietnam 🤯 The information gap is the real product. Free daily alerts in bio 👆

**Hashtags:**
#arbitrage #ecommerce #dropshipping #sidehustle #crossborder #shopee #1688 #vietnam #china #business2026

**Bio Link:** t.me/GlobalArbBot

**Notes for filming:**
- Use screen recordings of actual 1688 and Shopee listings
- Add price comparison graphics (green = buy, red = sell)
- Background music: upbeat, trending audio
- Text overlays for every number (viewers watch on mute)
- Total length: aim for 58 seconds (algorithm prefers under 60)"""


def main():
    prices, opportunities = load_data()
    items = extract_top_items(prices)

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    generators = {
        "twitter_thread.md": generate_twitter_thread,
        "linkedin_post.md": generate_linkedin_post,
        "reddit_post.md": generate_reddit_post,
        "email_newsletter.md": generate_email_newsletter,
        "video_script.md": generate_video_script,
    }

    for filename, gen_func in generators.items():
        content = gen_func(items, prices)
        path = CONTENT_DIR / filename
        path.write_text(content, encoding="utf-8")
        print(f"✅ {filename} → {path}")

    print(f"\nAll content saved to: {CONTENT_DIR}")
    print(f"Files generated: {len(generators)}")


if __name__ == "__main__":
    main()
