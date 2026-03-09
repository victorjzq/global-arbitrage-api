#!/usr/bin/env python3
"""
系统状态仪表盘 — 一键查看所有引擎运行状况
用法: python3 system_status.py
"""
import os
import json
import glob
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
SRC = BASE / "src"

def check_reports():
    """检查报告生成状况"""
    reports = sorted(glob.glob(str(DATA / "reports" / "*.md")))
    html_reports = sorted(glob.glob(str(DATA / "reports" / "*.html")))
    return {
        "md_reports": len(reports),
        "html_reports": len(html_reports),
        "latest": os.path.basename(reports[-1]) if reports else "none",
    }

def check_opportunities():
    """检查机会数据"""
    opps = sorted(glob.glob(str(DATA / "opportunities_*.md")))
    price_data = DATA / "price_comparison.json"
    return {
        "opportunity_files": len(opps),
        "price_comparison": price_data.exists(),
        "latest_opportunity": os.path.basename(opps[-1]) if opps else "none",
    }

def check_engines():
    """检查各引擎文件是否存在"""
    engines = {
        "arbitrage_scanner": SRC / "arbitrage_scanner.py",
        "daily_scan": SRC / "daily_scan.py",
        "arbitrage_api": SRC / "arbitrage_api.py",
        "telegram_bot": SRC / "telegram_bot.py",
        "polymarket_scanner": SRC / "prediction-markets" / "polymarket_scanner.py",
        "trend_gap_scanner": SRC / "trend_gap_scanner.py",
        "daily_engine": SRC / "daily_engine.py",
        "opportunity_ranker": SRC / "opportunity_ranker.py",
        "publish_report": SRC / "publish_report.py",
        "md_to_html": SRC / "md_to_html.py",
    }
    return {name: "✅" if path.exists() else "❌" for name, path in engines.items()}

def check_data_flywheel():
    """检查数据飞轮"""
    query_log = DATA / "user_queries.jsonl"
    subscribers = DATA / "subscribers.json"
    queries = 0
    subs = 0
    if query_log.exists():
        with open(query_log) as f:
            queries = sum(1 for _ in f)
    if subscribers.exists():
        with open(subscribers) as f:
            subs = len(json.load(f))
    return {"total_queries": queries, "subscribers": subs}

def check_revenue():
    """检查变现通道就绪状态"""
    channels = {
        "Gumroad listing": (SRC / "gumroad_listing.md").exists(),
        "Telegram bot": (SRC / "telegram_bot.py").exists(),
        "Report (EN)": len(glob.glob(str(DATA / "reports" / "*EN*"))) > 0,
        "Report (CN)": len(glob.glob(str(DATA / "reports" / "*CN*"))) > 0,
        "HTML export": len(glob.glob(str(DATA / "reports" / "*.html"))) > 0,
        "API server": (SRC / "arbitrage_api.py").exists(),
        "Fiverr gigs": (BASE / "docs" / "fiverr-gigs.md").exists(),
    }
    ready = sum(1 for v in channels.values() if v)
    return {"channels": channels, "ready": f"{ready}/{len(channels)}"}

def main():
    print("=" * 60)
    print("🌍 GLOBAL ARBITRAGE SYSTEM STATUS")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n📊 ENGINES:")
    engines = check_engines()
    for name, status in engines.items():
        print(f"  {status} {name}")

    print("\n📈 DATA:")
    opps = check_opportunities()
    for k, v in opps.items():
        print(f"  • {k}: {v}")

    print("\n📄 REPORTS:")
    reports = check_reports()
    for k, v in reports.items():
        print(f"  • {k}: {v}")

    print("\n💰 REVENUE CHANNELS:")
    rev = check_revenue()
    print(f"  Ready: {rev['ready']}")
    for ch, ok in rev["channels"].items():
        print(f"  {'✅' if ok else '❌'} {ch}")

    print("\n🔄 DATA FLYWHEEL:")
    fw = check_data_flywheel()
    for k, v in fw.items():
        print(f"  • {k}: {v}")

    # 总体就绪度
    engine_count = sum(1 for v in engines.values() if v == "✅")
    total = len(engines)
    pct = int(engine_count / total * 100)
    print(f"\n{'=' * 60}")
    print(f"⚡ SYSTEM READINESS: {engine_count}/{total} engines ({pct}%)")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
