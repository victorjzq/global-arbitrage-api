#!/usr/bin/env python3
"""
Multi-channel report publisher for Global Arbitrage.

Distributes arbitrage reports to:
  - Telegram channel
  - Reddit (via API)
  - Medium (via API)
  - Gumroad (product update)

Usage:
    python3 publish_report.py                    # publish latest to all channels
    python3 publish_report.py --channel telegram # single channel
    python3 publish_report.py --report path.md   # specific report
    python3 publish_report.py --dry-run          # preview without posting

Dependencies:
    pip3 install python-telegram-bot==22.3 requests

Environment variables (set what you need):
    TELEGRAM_BOT_TOKEN    - Telegram bot token
    TELEGRAM_CHANNEL_ID   - e.g. @global_arbitrage
    REDDIT_CLIENT_ID      - Reddit app client ID
    REDDIT_CLIENT_SECRET  - Reddit app secret
    REDDIT_USERNAME       - Reddit username
    REDDIT_PASSWORD       - Reddit password
    REDDIT_SUBREDDIT      - Target subreddit (default: arbitrage)
    MEDIUM_TOKEN          - Medium integration token
    MEDIUM_PUBLICATION_ID - Medium publication ID (optional)
    GUMROAD_ACCESS_TOKEN  - Gumroad API token
    GUMROAD_PRODUCT_ID    - Gumroad product ID
"""

import os
import sys
import glob
import json
import logging
import argparse
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"


# ---------------------------------------------------------------------------
# Report loader
# ---------------------------------------------------------------------------
def load_latest_report(lang: str = "EN", report_path: Optional[str] = None) -> tuple[str, str]:
    """
    Returns (title, body) of the latest report.
    """
    if report_path:
        p = Path(report_path)
    else:
        pattern = str(REPORTS_DIR / f"*-arbitrage-report-{lang}.md")
        files = sorted(glob.glob(pattern), reverse=True)
        if not files:
            raise FileNotFoundError(f"No reports found matching {pattern}")
        p = Path(files[0])

    content = p.read_text()
    lines = content.strip().split("\n")

    # Extract title from first heading
    title = "Global Arbitrage Report"
    for line in lines:
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break

    return title, content


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 4] + "\n..."


def _md_to_plain(text: str) -> str:
    """Minimal markdown to plain text."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# Channel: Telegram
# ---------------------------------------------------------------------------
def publish_telegram(title: str, body: str, dry_run: bool = False) -> bool:
    """Post report to Telegram channel."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")

    if not token or not channel_id:
        logger.warning("Telegram: TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set. Skipping.")
        return False

    # Format for Telegram (4096 char limit)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    header = f"Global Arbitrage Report - {date_str}\n{'=' * 40}\n\n"
    msg = header + _truncate(body, 4096 - len(header))

    if dry_run:
        logger.info(f"[DRY RUN] Telegram -> {channel_id}")
        logger.info(f"  Title: {title}")
        logger.info(f"  Length: {len(msg)} chars")
        return True

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": channel_id,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })

    if resp.status_code == 200:
        logger.info(f"Telegram: posted to {channel_id}")
        return True
    else:
        logger.error(f"Telegram error: {resp.status_code} {resp.text}")
        return False


# ---------------------------------------------------------------------------
# Channel: Reddit
# ---------------------------------------------------------------------------
def publish_reddit(title: str, body: str, dry_run: bool = False) -> bool:
    """Post report to Reddit subreddit."""
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    username = os.getenv("REDDIT_USERNAME", "")
    password = os.getenv("REDDIT_PASSWORD", "")
    subreddit = os.getenv("REDDIT_SUBREDDIT", "arbitrage")

    if not all([client_id, client_secret, username, password]):
        logger.warning("Reddit: credentials not fully set. Skipping.")
        return False

    if dry_run:
        logger.info(f"[DRY RUN] Reddit -> r/{subreddit}")
        logger.info(f"  Title: {title}")
        logger.info(f"  Body length: {len(body)} chars")
        return True

    # OAuth token
    auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
    headers = {"User-Agent": "GlobalArbitrageBot/1.0"}
    token_resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=auth,
        data={"grant_type": "password", "username": username, "password": password},
        headers=headers,
    )

    if token_resp.status_code != 200:
        logger.error(f"Reddit auth failed: {token_resp.status_code}")
        return False

    access_token = token_resp.json().get("access_token")
    headers["Authorization"] = f"Bearer {access_token}"

    # Reddit has a 40000 char limit for self posts
    post_body = _truncate(body, 39000)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    post_title = f"[{date_str}] {title}"

    resp = requests.post(
        "https://oauth.reddit.com/api/submit",
        headers=headers,
        data={
            "sr": subreddit,
            "kind": "self",
            "title": post_title,
            "text": post_body,
            "sendreplies": True,
        },
    )

    if resp.status_code == 200 and not resp.json().get("json", {}).get("errors"):
        post_url = resp.json()["json"]["data"]["url"]
        logger.info(f"Reddit: posted to r/{subreddit} -> {post_url}")
        return True
    else:
        logger.error(f"Reddit post failed: {resp.text}")
        return False


# ---------------------------------------------------------------------------
# Channel: Medium
# ---------------------------------------------------------------------------
def publish_medium(title: str, body: str, dry_run: bool = False) -> bool:
    """Create a draft post on Medium."""
    token = os.getenv("MEDIUM_TOKEN", "")
    publication_id = os.getenv("MEDIUM_PUBLICATION_ID", "")

    if not token:
        logger.warning("Medium: MEDIUM_TOKEN not set. Skipping.")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if dry_run:
        logger.info("[DRY RUN] Medium draft")
        logger.info(f"  Title: {title}")
        logger.info(f"  Body length: {len(body)} chars")
        return True

    # Get user ID
    me_resp = requests.get("https://api.medium.com/v1/me", headers=headers)
    if me_resp.status_code != 200:
        logger.error(f"Medium auth failed: {me_resp.status_code}")
        return False

    user_id = me_resp.json()["data"]["id"]

    # Determine endpoint (user or publication)
    if publication_id:
        url = f"https://api.medium.com/v1/publications/{publication_id}/posts"
    else:
        url = f"https://api.medium.com/v1/users/{user_id}/posts"

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    post_data = {
        "title": f"{title} - {date_str}",
        "contentFormat": "markdown",
        "content": body,
        "tags": ["arbitrage", "trading", "market-analysis", "finance"],
        "publishStatus": "draft",  # draft first, review before publishing
    }

    resp = requests.post(url, headers=headers, json=post_data)

    if resp.status_code in (200, 201):
        post_url = resp.json()["data"]["url"]
        logger.info(f"Medium: draft created -> {post_url}")
        return True
    else:
        logger.error(f"Medium post failed: {resp.status_code} {resp.text}")
        return False


# ---------------------------------------------------------------------------
# Channel: Gumroad (product update / ping buyers)
# ---------------------------------------------------------------------------
def publish_gumroad(title: str, body: str, dry_run: bool = False) -> bool:
    """Update Gumroad product or send update to buyers."""
    token = os.getenv("GUMROAD_ACCESS_TOKEN", "")
    product_id = os.getenv("GUMROAD_PRODUCT_ID", "")

    if not token or not product_id:
        logger.warning("Gumroad: credentials not set. Skipping.")
        return False

    if dry_run:
        logger.info(f"[DRY RUN] Gumroad product update: {product_id}")
        logger.info(f"  Title: {title}")
        return True

    headers = {"Authorization": f"Bearer {token}"}

    # Send product update to all buyers
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    update_data = {
        "product_id": product_id,
        "title": f"New Report: {title} ({date_str})",
        "message": _truncate(_md_to_plain(body), 5000),
    }

    resp = requests.post(
        f"https://api.gumroad.com/v2/products/{product_id}/subscribers",
        headers=headers,
        data=update_data,
    )

    if resp.status_code == 200:
        logger.info(f"Gumroad: update sent for product {product_id}")
        return True
    else:
        logger.error(f"Gumroad update failed: {resp.status_code} {resp.text}")
        return False


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
CHANNELS = {
    "telegram": publish_telegram,
    "reddit": publish_reddit,
    "medium": publish_medium,
    "gumroad": publish_gumroad,
}


def publish_all(
    title: str,
    body: str,
    channels: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, bool]:
    """Publish to all (or specified) channels. Returns {channel: success}."""
    targets = channels or list(CHANNELS.keys())
    results = {}

    for ch in targets:
        if ch not in CHANNELS:
            logger.warning(f"Unknown channel: {ch}")
            results[ch] = False
            continue

        try:
            results[ch] = CHANNELS[ch](title, body, dry_run=dry_run)
        except Exception as e:
            logger.error(f"{ch} failed with exception: {e}")
            results[ch] = False

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Publish arbitrage report to multiple channels")
    parser.add_argument("--report", type=str, help="Path to specific report file")
    parser.add_argument("--lang", type=str, default="EN", choices=["EN", "CN"], help="Report language")
    parser.add_argument(
        "--channel",
        type=str,
        nargs="+",
        choices=list(CHANNELS.keys()),
        help="Specific channel(s) to publish to",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--list-channels", action="store_true", help="List available channels")

    args = parser.parse_args()

    if args.list_channels:
        print("Available channels:")
        for ch in CHANNELS:
            print(f"  - {ch}")
        return

    try:
        title, body = load_latest_report(lang=args.lang, report_path=args.report)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"Report: {title}")
    logger.info(f"Length: {len(body)} chars")

    if args.dry_run:
        logger.info("=== DRY RUN MODE ===")

    results = publish_all(title, body, channels=args.channel, dry_run=args.dry_run)

    print("\n--- Results ---")
    for ch, ok in results.items():
        status = "OK" if ok else "SKIP/FAIL"
        print(f"  {ch}: {status}")

    success_count = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n{success_count}/{total} channels published successfully.")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
