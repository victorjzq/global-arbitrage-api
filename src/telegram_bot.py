#!/usr/bin/env python3
"""
Global Arbitrage Telegram Bot
Subscription-based arbitrage opportunity alerts.

Usage:
    export TELEGRAM_BOT_TOKEN="your-bot-token"
    export STRIPE_SECRET_KEY="sk_..."  # optional, for payments
    python3 telegram_bot.py

Dependencies:
    pip3 install python-telegram-bot==22.3 stripe
"""

import os
import json
import glob
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"
SUBSCRIBERS_FILE = Path(__file__).resolve().parent.parent / "data" / "subscribers.json"
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")  # e.g. @global_arbitrage

# Subscription tiers
TIERS = {
    "free": {"name": "Free", "price": 0, "features": ["Daily top-3 opportunities"]},
    "pro": {
        "name": "Pro",
        "price": 29,
        "features": [
            "All opportunities with full analysis",
            "Real-time alerts",
            "Weekly deep-dive report",
        ],
    },
    "premium": {
        "name": "Premium",
        "price": 99,
        "features": [
            "Everything in Pro",
            "Custom market watchlist",
            "1-on-1 monthly strategy call",
            "API access",
        ],
    },
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subscriber persistence (JSON file, swap for DB in production)
# ---------------------------------------------------------------------------
def _load_subscribers() -> dict:
    if SUBSCRIBERS_FILE.exists():
        return json.loads(SUBSCRIBERS_FILE.read_text())
    return {}


def _save_subscribers(data: dict):
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIBERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _get_user_tier(user_id: int) -> str:
    subs = _load_subscribers()
    entry = subs.get(str(user_id), {})
    if not entry:
        return "free"
    expires = entry.get("expires")
    if expires and datetime.fromisoformat(expires) < datetime.utcnow():
        return "free"
    return entry.get("tier", "free")


def _set_user_tier(user_id: int, tier: str, days: int = 30):
    subs = _load_subscribers()
    subs[str(user_id)] = {
        "tier": tier,
        "subscribed_at": datetime.utcnow().isoformat(),
        "expires": (datetime.utcnow() + timedelta(days=days)).isoformat(),
    }
    _save_subscribers(subs)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------
def _latest_report(lang: str = "EN") -> Optional[str]:
    """Find the most recent report file."""
    pattern = str(REPORTS_DIR / f"*-arbitrage-report-{lang}.md")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        return None
    return Path(files[0]).read_text()


def _top_opportunities(n: int = 3) -> str:
    """Extract top N opportunities from latest report."""
    report = _latest_report("CN") or _latest_report("EN")
    if not report:
        return "No report available yet. Check back tomorrow."

    # Simple extraction: return first n sections that look like opportunities
    lines = report.split("\n")
    result_lines = []
    count = 0
    in_opportunity = False

    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if count >= n:
                break
            in_opportunity = True
            count += 1
            result_lines.append("")
            result_lines.append(line)
        elif in_opportunity:
            result_lines.append(line)

    if not result_lines:
        # Fallback: return first 1500 chars
        return report[:1500]

    return "\n".join(result_lines).strip()


# ---------------------------------------------------------------------------
# Bot commands
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"Welcome {user.first_name}! 🌏\n\n"
        "I scan 1688/Alibaba vs Shopee/TikTok Shop prices across 9 trade routes "
        "and find 2-5x price gaps you can profit from.\n\n"
        "📋 Commands:\n"
        "/sample - Free preview (top 3 opportunities)\n"
        "/opportunities - Today's arbitrage plays\n"
        "/report - Full PDF report (Pro/Premium)\n"
        "/subscribe - View plans & pricing\n"
        "/status - Your subscription\n\n"
        "🆓 Start with /sample to see today's best opportunities!"
    )
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_opportunities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tier = _get_user_tier(user_id)

    n = 3 if tier == "free" else 10
    opps = _top_opportunities(n)

    header = f"Top arbitrage opportunities ({tier.upper()} tier):\n"
    if tier == "free":
        footer = "\n\n--- Upgrade to Pro for all opportunities: /subscribe ---"
    else:
        footer = ""

    # Telegram message limit is 4096 chars
    msg = header + opps + footer
    if len(msg) > 4096:
        msg = msg[:4090] + "\n..."

    await update.message.reply_text(msg)


def _latest_pdf(lang: str = "EN") -> Optional[Path]:
    """Find the most recent PDF report."""
    pattern = str(REPORTS_DIR / f"*-arbitrage-report-{lang}.pdf")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None


async def cmd_sample(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Free sample — top 3 opportunities + CTA to subscribe."""
    opps = _top_opportunities(3)
    text = (
        "🔥 *Free Sample — Top 3 Arbitrage Opportunities*\n\n"
        f"{opps}\n\n"
        "---\n"
        "📊 Full report includes:\n"
        "• 5 deep-dive opportunities with supplier links\n"
        "• 10 trending products (China hot → SEA unsaturated)\n"
        "• Platform fee comparison (Shopee vs TikTok Shop vs Lazada)\n"
        "• Risk analysis + 4-week action plan\n\n"
        "💰 Get the full PDF report: /subscribe ($9 one-time)\n"
        "📈 Or get weekly updates: /subscribe ($29/mo Pro)"
    )
    if len(text) > 4096:
        text = text[:4090] + "\n..."
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tier = _get_user_tier(user_id)

    if tier == "free":
        await update.message.reply_text(
            "📊 Full reports are for Pro/Premium subscribers.\n\n"
            "Try /sample for a free preview!\n"
            "Or /subscribe to get the full PDF report.\n\n"
            "💡 One-time report: $9\n"
            "📈 Pro (weekly updates): $29/mo"
        )
        return

    # Try to send PDF first (better experience)
    lang = "CN" if context.args and "cn" in " ".join(context.args).lower() else "EN"
    pdf = _latest_pdf(lang)
    if pdf and pdf.exists():
        await update.message.reply_document(
            document=open(pdf, "rb"),
            filename=f"Global-Arbitrage-Report-{datetime.utcnow().strftime('%Y-%m-%d')}-{lang}.pdf",
            caption=f"📊 Global Arbitrage Report ({lang}) — {datetime.utcnow().strftime('%B %Y')}",
        )
        return

    # Fallback to markdown
    report = _latest_report(lang)
    if not report:
        await update.message.reply_text("No report available yet.")
        return

    if len(report) > 4096:
        report_path = REPORTS_DIR / "latest_report.md"
        report_path.write_text(report)
        await update.message.reply_document(
            document=open(report_path, "rb"),
            filename=f"arbitrage-report-{datetime.utcnow().strftime('%Y-%m-%d')}.md",
            caption="Latest Global Arbitrage Report",
        )
    else:
        await update.message.reply_text(report)


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Pro - $29/mo", callback_data="subscribe_pro"),
            InlineKeyboardButton("Premium - $99/mo", callback_data="subscribe_premium"),
        ],
        [
            InlineKeyboardButton("Pay with Crypto (USDT)", callback_data="subscribe_crypto"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "Choose your plan:\n\n"
    for tid, t in TIERS.items():
        features = "\n  ".join(f"- {f}" for f in t["features"])
        price = f"${t['price']}/mo" if t["price"] > 0 else "Free"
        text += f"*{t['name']}* ({price}):\n  {features}\n\n"

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tier = _get_user_tier(user_id)
    subs = _load_subscribers()
    entry = subs.get(str(user_id), {})

    if tier == "free":
        text = "You're on the Free tier.\nUse /subscribe to upgrade."
    else:
        expires = entry.get("expires", "N/A")
        text = f"Tier: {tier.upper()}\nExpires: {expires}\n\nThank you for subscribing!"

    await update.message.reply_text(text)


# ---------------------------------------------------------------------------
# Payment callbacks
# ---------------------------------------------------------------------------
async def handle_subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "subscribe_pro":
        await _initiate_payment(query, "pro", 29)
    elif data == "subscribe_premium":
        await _initiate_payment(query, "premium", 99)
    elif data == "subscribe_crypto":
        await query.edit_message_text(
            "Crypto payment:\n\n"
            "Send USDT (ERC-20/Base/Polygon) to:\n"
            "`0x49Df862A9c9C8bDbE54e2Ae47283e59446817bdf`\n\n"
            "After payment, send your TX hash here.\n"
            "We'll activate within 1 hour.",
            parse_mode="Markdown",
        )
    elif data.startswith("confirm_stripe_"):
        tier = data.replace("confirm_stripe_", "")
        # In production: verify Stripe payment intent here
        _set_user_tier(query.from_user.id, tier, days=30)
        await query.edit_message_text(
            f"Payment confirmed! You're now on the {tier.upper()} plan.\n"
            "Use /opportunities to see all available plays."
        )


async def _initiate_payment(query, tier: str, amount: int):
    """Create Stripe checkout or show payment link."""
    if STRIPE_SECRET_KEY:
        # Production: create Stripe checkout session
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Global Arbitrage {tier.upper()} Plan"},
                        "unit_amount": amount * 100,
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }],
                mode="subscription",
                success_url="https://t.me/your_bot?start=paid",
                cancel_url="https://t.me/your_bot?start=cancelled",
                metadata={"user_id": str(query.from_user.id), "tier": tier},
            )
            keyboard = [[InlineKeyboardButton("Pay Now", url=session.url)]]
            await query.edit_message_text(
                f"Click below to subscribe to {tier.upper()} (${amount}/mo):",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error(f"Stripe error: {e}")
            await query.edit_message_text(f"Payment error. Contact support.\n{e}")
    else:
        # Demo mode: instant activation
        keyboard = [
            [InlineKeyboardButton(
                f"Activate {tier.upper()} (demo)",
                callback_data=f"confirm_stripe_{tier}",
            )]
        ]
        await query.edit_message_text(
            f"Stripe not configured. Demo mode.\n"
            f"Click to activate {tier.upper()} for free:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# ---------------------------------------------------------------------------
# Webhook for Stripe (run alongside or as separate endpoint)
# ---------------------------------------------------------------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle arbitrary text - check for crypto TX hashes."""
    text = update.message.text.strip()
    # Simple TX hash detection (64 hex chars)
    if len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
        await update.message.reply_text(
            "TX hash received. We'll verify and activate your subscription within 1 hour.\n"
            "Contact @victorjia if not activated."
        )
        # In production: queue for verification
        logger.info(f"Crypto TX from {update.effective_user.id}: {text}")
    else:
        await update.message.reply_text(
            "I don't understand that. Use /help to see available commands."
        )


# ---------------------------------------------------------------------------
# Channel broadcasting (called by publish_report.py or cron)
# ---------------------------------------------------------------------------
async def broadcast_to_channel(app: Application, text: str):
    """Post to the public Telegram channel."""
    if not CHANNEL_ID:
        logger.warning("TELEGRAM_CHANNEL_ID not set, skipping broadcast")
        return
    bot = app.bot
    if len(text) > 4096:
        text = text[:4090] + "\n..."
    await bot.send_message(chat_id=CHANNEL_ID, text=text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not BOT_TOKEN:
        print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable")
        print("  1. Talk to @BotFather on Telegram")
        print("  2. Create a bot and get the token")
        print("  3. export TELEGRAM_BOT_TOKEN='your-token'")
        return

    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("sample", cmd_sample))
    app.add_handler(CommandHandler("opportunities", cmd_opportunities))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("status", cmd_status))

    # Callbacks (subscription buttons)
    app.add_handler(CallbackQueryHandler(handle_subscribe_callback))

    # Text handler (crypto TX, etc.)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting... Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
