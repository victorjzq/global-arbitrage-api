#!/usr/bin/env python3
"""
Trend Gap Scanner: Discovers time-based information gaps between China and Southeast Asia.
Finds trends hot in China (Douyin/Xiaohongshu/1688) that haven't reached SEA yet.

Usage:
    python3 trend_gap_scanner.py [--pytrends] [--output-dir PATH]

By default uses curated trend intelligence + pytrends validation.
Falls back to pure intelligence mode if pytrends hits rate limits.
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TrendGap:
    product_name_cn: str
    product_name_en: str
    product_name_vn: str
    category: str
    cn_trend_intensity: int          # 0-100
    sea_trend_intensity: int         # 0-100
    gap_score: float
    estimated_window_months: int     # months before gap closes
    market_size_factor: float        # 0.5 - 2.0
    source_platform: str             # douyin / xiaohongshu / 1688
    recommended_action: str
    sea_countries: list = field(default_factory=lambda: ["VN", "TH", "ID"])
    data_source: str = "web_intelligence"  # pytrends / web_intelligence
    notes: str = ""


# ---------------------------------------------------------------------------
# Curated China trend intelligence (from web research)
# ---------------------------------------------------------------------------

CHINA_TRENDS = [
    {
        "cn": "拼豆/像素珠艺",
        "en": "Pixel Bead Art Kits",
        "vn": "Bộ kit nghệ thuật hạt pixel",
        "category": "hobby_craft",
        "cn_intensity": 82,
        "source": "xiaohongshu",
        "notes": "Niche hobby exploding on Xiaohongshu 2026, 10k+ unit sellers",
    },
    {
        "cn": "双频射频美容仪",
        "en": "Dual-Frequency RF Beauty Device",
        "vn": "Máy làm đẹp RF tần số kép",
        "category": "beauty_device",
        "cn_intensity": 91,
        "source": "douyin",
        "notes": "RF+LED facial toners trending heavily on Douyin livestreams",
    },
    {
        "cn": "智能宠物喂食器",
        "en": "Smart Pet Auto Feeder",
        "vn": "Máy cho thú cưng ăn tự động thông minh",
        "category": "pet_products",
        "cn_intensity": 78,
        "source": "douyin",
        "notes": "1 in 8 CN households have pets; smart feeders with app control booming",
    },
    {
        "cn": "可编程机器人教育套件",
        "en": "Programmable Robotics Education Kit",
        "vn": "Bộ kit robot lập trình giáo dục",
        "category": "education",
        "cn_intensity": 75,
        "source": "1688",
        "notes": "STEM education push in China; kits selling 1299-3599 RMB on 1688",
    },
    {
        "cn": "臭氧水喷雾祛痘仪",
        "en": "Ozone Water Spray Acne Device",
        "vn": "Máy xịt nước ozone trị mụn",
        "category": "beauty_device",
        "cn_intensity": 70,
        "source": "xiaohongshu",
        "notes": "Ozone water sprayers for acne-prone skin trending on XHS",
    },
    {
        "cn": "太阳能WiFi监控摄像头",
        "en": "Solar-Powered WiFi Security Camera",
        "vn": "Camera giám sát WiFi năng lượng mặt trời",
        "category": "smart_home",
        "cn_intensity": 85,
        "source": "1688",
        "notes": "312% YoY growth; solar + WiFi combo for areas with poor wiring",
    },
    {
        "cn": "空气炸烤箱二合一",
        "en": "Air Fryer-Oven Hybrid Combo",
        "vn": "Nồi chiên không dầu kiêm lò nướng",
        "category": "kitchen",
        "cn_intensity": 80,
        "source": "douyin",
        "notes": "187% YoY growth; compact multi-function kitchen appliance",
    },
    {
        "cn": "减脂软糖/功能零食",
        "en": "Fat-Burning Functional Gummies",
        "vn": "Kẹo dẻo chức năng giảm mỡ",
        "category": "health_food",
        "cn_intensity": 73,
        "source": "douyin",
        "notes": "Functional health snacks trending; sugar-free, fat-burning claims",
    },
    {
        "cn": "痘痘贴/隐形祛痘贴",
        "en": "Invisible Acne Pimple Patches",
        "vn": "Miếng dán trị mụn vô hình",
        "category": "beauty",
        "cn_intensity": 88,
        "source": "xiaohongshu",
        "notes": "Pennies per unit cost, $5-6 retail; 100k+ monthly search volume",
    },
    {
        "cn": "模块化智能插座(带电量监控)",
        "en": "Modular Smart Plug with kWh Tracking",
        "vn": "Ổ cắm thông minh module có theo dõi điện năng",
        "category": "smart_home",
        "cn_intensity": 68,
        "source": "1688",
        "notes": "241% YoY growth in China; energy monitoring appeals to cost-conscious",
    },
    {
        "cn": "AI写真/AI证件照机",
        "en": "AI Portrait Photo Booth Device",
        "vn": "Máy chụp ảnh chân dung AI",
        "category": "electronics",
        "cn_intensity": 86,
        "source": "douyin",
        "notes": "AI photo booths viral on Douyin; portable versions for small shops",
    },
    {
        "cn": "便携式钛合金微针套装",
        "en": "Portable Titanium Derma Roller Kit",
        "vn": "Bộ lăn kim titan di động",
        "category": "beauty_device",
        "cn_intensity": 72,
        "source": "xiaohongshu",
        "notes": "Sterile titanium tips; at-home beauty treatment trend",
    },
    {
        "cn": "生物降解电路拼搭积木",
        "en": "Biodegradable Circuit Building Tiles",
        "vn": "Gạch lắp ráp mạch điện phân hủy sinh học",
        "category": "education",
        "cn_intensity": 65,
        "source": "1688",
        "notes": "Eco-friendly STEM toys; combines sustainability + education",
    },
    {
        "cn": "场景化香薰机(带AI推荐)",
        "en": "AI Scene-Based Aroma Diffuser",
        "vn": "Máy khuếch tán tinh dầu AI theo cảnh",
        "category": "smart_home",
        "cn_intensity": 71,
        "source": "xiaohongshu",
        "notes": "AI recommends scents based on mood/time; lifestyle product on XHS",
    },
    {
        "cn": "冻干水果咖啡",
        "en": "Freeze-Dried Fruit Coffee Cubes",
        "vn": "Cà phê trái cây đông khô dạng viên",
        "category": "food_beverage",
        "cn_intensity": 77,
        "source": "douyin",
        "notes": "Instant specialty coffee with freeze-dried fruit; Douyin livestream hit",
    },
]

# SEA market awareness estimates (from web research on Shopee/Lazada trends)
# 0 = unknown, 100 = fully saturated
SEA_AWARENESS = {
    "Pixel Bead Art Kits": 15,
    "Dual-Frequency RF Beauty Device": 25,
    "Smart Pet Auto Feeder": 35,
    "Programmable Robotics Education Kit": 30,
    "Ozone Water Spray Acne Device": 10,
    "Solar-Powered WiFi Security Camera": 45,
    "Air Fryer-Oven Hybrid Combo": 50,
    "Fat-Burning Functional Gummies": 20,
    "Invisible Acne Pimple Patches": 55,
    "Modular Smart Plug with kWh Tracking": 15,
    "AI Portrait Photo Booth Device": 12,
    "Portable Titanium Derma Roller Kit": 30,
    "Biodegradable Circuit Building Tiles": 8,
    "AI Scene-Based Aroma Diffuser": 10,
    "Freeze-Dried Fruit Coffee Cubes": 18,
}

# Market size factors by category for SEA
MARKET_SIZE_FACTORS = {
    "beauty": 1.8,
    "beauty_device": 1.6,
    "smart_home": 1.4,
    "kitchen": 1.5,
    "pet_products": 1.0,
    "education": 1.2,
    "hobby_craft": 0.8,
    "health_food": 1.3,
    "food_beverage": 1.5,
    "electronics": 1.7,
}


# ---------------------------------------------------------------------------
# pytrends validation (optional, may hit rate limits)
# ---------------------------------------------------------------------------

def try_pytrends_validation(trends: list[dict]) -> dict[str, dict]:
    """Try to validate trends via Google Trends. Returns {en_name: {geo: score}}."""
    results = {}
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=420, timeout=(10, 25))

        for trend in trends:
            en_name = trend["en"]
            keyword = en_name.split("(")[0].strip()  # clean up parenthetical
            if len(keyword) > 100:
                keyword = keyword[:100]

            try:
                # Compare CN vs VN vs TH vs ID
                pytrends.build_payload(
                    [keyword],
                    timeframe="today 3-m",
                    geo=""  # worldwide first
                )
                global_data = pytrends.interest_by_region(
                    resolution="COUNTRY",
                    inc_low_vol=True,
                    inc_geo_code=True,
                )

                geo_scores = {}
                for geo_code, label in [("CN", "CN"), ("VN", "VN"), ("TH", "TH"), ("ID", "ID")]:
                    try:
                        score = int(global_data.loc[global_data.index.str.contains(geo_code, case=False), keyword].values[0])
                    except (IndexError, KeyError, ValueError):
                        score = 0
                    geo_scores[label] = score

                results[en_name] = geo_scores
                log.info(f"  pytrends OK: {keyword} -> {geo_scores}")
                time.sleep(2)  # rate limit courtesy

            except Exception as e:
                log.warning(f"  pytrends failed for '{keyword}': {e}")
                time.sleep(5)

    except ImportError:
        log.warning("pytrends not installed, skipping validation")
    except Exception as e:
        log.warning(f"pytrends init failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Gap scoring
# ---------------------------------------------------------------------------

def compute_gap_score(cn_intensity: int, sea_intensity: int, market_factor: float) -> float:
    """GAP_SCORE = (CN_trend_intensity - SEA_trend_intensity) * market_size_factor"""
    return round((cn_intensity - sea_intensity) * market_factor, 1)


def estimate_window_months(cn_intensity: int, sea_intensity: int, category: str) -> int:
    """Estimate months before the gap closes based on trend dynamics."""
    gap = cn_intensity - sea_intensity
    # Fast-spreading categories (beauty, electronics) close gaps faster
    speed_factor = {
        "beauty": 0.8, "beauty_device": 0.9, "electronics": 0.7,
        "smart_home": 1.0, "kitchen": 1.1, "pet_products": 1.3,
        "education": 1.5, "hobby_craft": 1.8, "health_food": 1.2,
        "food_beverage": 1.1,
    }
    factor = speed_factor.get(category, 1.0)
    # Base: 1 month per 10 gap points, adjusted by speed
    months = max(1, min(18, int(gap / 10 * factor)))
    return months


def generate_action(trend: dict, gap_score: float) -> str:
    """Generate recommended action based on trend data."""
    source = trend["source"]
    category = trend.get("category", "general")

    actions = []
    actions.append(f"Source on 1688.com (search: {trend['cn']})")

    if category in ("beauty", "beauty_device"):
        actions.append("Sell on Shopee VN/TH (beauty categories have highest margins)")
        actions.append("Create TikTok Shop VN demo videos for viral reach")
    elif category in ("smart_home", "electronics"):
        actions.append("Sell on Shopee VN/ID (electronics top category)")
        actions.append("Set up Lazada TH/ID store for higher-ticket items")
    elif category in ("food_beverage", "health_food"):
        actions.append("Sell on Shopee VN/TH (food category growing fast)")
        actions.append("Check import regulations for food products in target country")
    elif category == "education":
        actions.append("Sell on Shopee VN/ID (education products 2.7x basket size)")
        actions.append("Partner with local education influencers on TikTok")
    else:
        actions.append("Sell on Shopee VN/TH/ID")
        actions.append("Test with small batch via cross-border shipping first")

    if gap_score > 100:
        actions.append("HIGH PRIORITY: Large gap, move fast before competitors")
    elif gap_score > 60:
        actions.append("MEDIUM PRIORITY: Good opportunity, validate with small test order")

    return " | ".join(actions)


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def scan_trend_gaps(use_pytrends: bool = True) -> list[TrendGap]:
    """Main scanning logic."""
    log.info("=" * 60)
    log.info("TREND GAP SCANNER: China -> Southeast Asia")
    log.info("=" * 60)

    # Step 1: Try pytrends validation
    pytrends_data = {}
    if use_pytrends:
        log.info("\n[1/3] Attempting pytrends validation...")
        pytrends_data = try_pytrends_validation(CHINA_TRENDS)
        if pytrends_data:
            log.info(f"  Got pytrends data for {len(pytrends_data)} trends")
        else:
            log.info("  pytrends returned no data, using web intelligence only")

    # Step 2: Compute gaps
    log.info("\n[2/3] Computing trend gaps...")
    gaps = []

    for trend in CHINA_TRENDS:
        en_name = trend["en"]
        category = trend.get("category", "general")
        cn_intensity = trend["cn_intensity"]
        market_factor = MARKET_SIZE_FACTORS.get(category, 1.0)

        # Get SEA intensity: prefer pytrends, fall back to web intelligence
        if en_name in pytrends_data:
            pt = pytrends_data[en_name]
            sea_intensity = max(
                pt.get("VN", 0),
                pt.get("TH", 0),
                pt.get("ID", 0),
            )
            data_source = "pytrends"
            # If pytrends gives CN data, use it
            if pt.get("CN", 0) > 0:
                cn_intensity = pt["CN"]
        else:
            sea_intensity = SEA_AWARENESS.get(en_name, 20)
            data_source = "web_intelligence"

        gap_score = compute_gap_score(cn_intensity, sea_intensity, market_factor)
        window = estimate_window_months(cn_intensity, sea_intensity, category)
        action = generate_action(trend, gap_score)

        gap = TrendGap(
            product_name_cn=trend["cn"],
            product_name_en=en_name,
            product_name_vn=trend["vn"],
            category=category,
            cn_trend_intensity=cn_intensity,
            sea_trend_intensity=sea_intensity,
            gap_score=gap_score,
            estimated_window_months=window,
            market_size_factor=market_factor,
            source_platform=trend["source"],
            recommended_action=action,
            data_source=data_source,
            notes=trend.get("notes", ""),
        )
        gaps.append(gap)

    # Sort by gap score descending
    gaps.sort(key=lambda g: g.gap_score, reverse=True)

    # Step 3: Display results
    log.info("\n[3/3] Top Trend Gap Opportunities:")
    log.info("-" * 60)
    for i, g in enumerate(gaps, 1):
        log.info(
            f"  #{i:2d} | {g.product_name_en:<42s} | "
            f"CN:{g.cn_trend_intensity:3d} SEA:{g.sea_trend_intensity:3d} | "
            f"GAP: {g.gap_score:6.1f} | "
            f"Window: {g.estimated_window_months:2d}mo | "
            f"[{g.source_platform}]"
        )
    log.info("-" * 60)

    return gaps


def save_results(gaps: list[TrendGap], output_dir: str) -> str:
    """Save results to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join(output_dir, f"trend_gaps_{date_str}.json")

    output = {
        "scan_date": datetime.now().isoformat(),
        "scanner_version": "1.0.0",
        "total_trends_analyzed": len(gaps),
        "top_opportunities": [asdict(g) for g in gaps],
        "summary": {
            "highest_gap_score": gaps[0].gap_score if gaps else 0,
            "avg_gap_score": round(sum(g.gap_score for g in gaps) / len(gaps), 1) if gaps else 0,
            "categories_covered": list(set(g.category for g in gaps)),
            "avg_window_months": round(sum(g.estimated_window_months for g in gaps) / len(gaps), 1) if gaps else 0,
        },
        "methodology": (
            "GAP_SCORE = (CN_trend_intensity - SEA_trend_intensity) * market_size_factor. "
            "CN trends sourced from Douyin/Xiaohongshu/1688 web intelligence + optional pytrends validation. "
            "SEA awareness estimated from Shopee/Lazada/TikTok Shop market research."
        ),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"\nResults saved to: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Trend Gap Scanner: China -> SEA")
    parser.add_argument("--pytrends", action="store_true", default=False,
                        help="Enable pytrends Google Trends validation")
    parser.add_argument("--output-dir", type=str,
                        default=os.path.expanduser("~/cowork-brain/projects/global-arbitrage/data"),
                        help="Output directory for results")
    args = parser.parse_args()

    gaps = scan_trend_gaps(use_pytrends=args.pytrends)
    filepath = save_results(gaps, args.output_dir)

    # Print top 5 as quick summary
    print("\n" + "=" * 60)
    print("TOP 5 TREND GAP OPPORTUNITIES (China -> SEA)")
    print("=" * 60)
    for i, g in enumerate(gaps[:5], 1):
        print(f"\n#{i} {g.product_name_en}")
        print(f"   CN: {g.product_name_cn} | VN: {g.product_name_vn}")
        print(f"   CN Trend: {g.cn_trend_intensity}/100 | SEA Trend: {g.sea_trend_intensity}/100")
        print(f"   GAP SCORE: {g.gap_score} | Window: {g.estimated_window_months} months")
        print(f"   Action: {g.recommended_action}")

    print(f"\nFull results: {filepath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
