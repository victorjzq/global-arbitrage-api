#!/usr/bin/env python3
"""把套利报告发到 Dev.to — 有自然流量的平台"""
import os
import json
import requests
from pathlib import Path

ENV_FILE = Path(os.path.expanduser("~/dev/Claude-Global/公众号国际化/.env"))
REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"

def get_key():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "DEVTO_API_KEY" in line and "=" in line:
                return line.split("=", 1)[1].strip()
    return os.environ.get("DEVTO_API_KEY", "")

def publish(api_key, title, markdown, tags):
    resp = requests.post(
        "https://dev.to/api/articles",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={
            "article": {
                "title": title,
                "body_markdown": markdown,
                "published": True,
                "tags": tags[:4],  # Dev.to max 4 tags
            }
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("url", ""), data.get("id", "")

def main():
    key = get_key()
    if not key:
        print("❌ No DEVTO_API_KEY")
        return

    # 发英文报告
    en_reports = sorted(REPORT_DIR.glob("*EN*.md"))
    if not en_reports:
        print("❌ No EN reports")
        return

    report = en_reports[-1]
    md = report.read_text()

    title = "I Built an AI That Finds 3-5x Price Gaps Between China and Southeast Asia — Here's the Data"
    tags = ["ecommerce", "ai", "business", "data"]

    # 在报告末尾加 CTA
    cta = """

---

## Want Daily Updates?

I run this scanner every 6 hours and publish new opportunities.

- **Free newsletter**: [victorjia.substack.com](https://victorjia.substack.com)
- **Full report with supplier links**: DM me or check my profile

*Built with Python + Claude AI. The scanner is open source — happy to share the code if there's interest.*
"""
    md_with_cta = md + cta

    print(f"📝 Publishing to Dev.to: {title[:50]}...")
    try:
        url, article_id = publish(key, title, md_with_cta, tags)
        print(f"✅ Published: {url}")
        print(f"   ID: {article_id}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        # 如果标题重复，换个标题试
        if "422" in str(e):
            title = f"Cross-Border E-Commerce Arbitrage: China to SEA (March 2026 Data)"
            try:
                url, article_id = publish(key, title, md_with_cta, tags)
                print(f"✅ Published with alt title: {url}")
            except Exception as e2:
                print(f"❌ Also failed: {e2}")

if __name__ == "__main__":
    main()
