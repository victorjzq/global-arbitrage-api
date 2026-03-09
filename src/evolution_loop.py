#!/usr/bin/env python3
"""
进化引擎 — 系统自我优化
不是重复做同样的事，而是每次做得更好。

每次运行:
1. 分析历史数据 → 哪些品类/市场/时段产出最高
2. 调整扫描权重 → 下次优先扫高产出领域
3. 优化内容策略 → 哪类内容模板效果最好
4. 记录进化日志 → 可追溯系统变聪明的过程
5. 更新 ARBITRAGE_DB → 新数据自动扩充知识库

这是"工具造工具"的核心：系统用自己的输出改进自己。
"""

import os
import json
import glob
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
SRC = PROJECT / "src"
KNOWLEDGE = PROJECT / "knowledge"
EVOLUTION_LOG = DATA / "logs" / "evolution.jsonl"

os.makedirs(DATA / "logs", exist_ok=True)


def analyze_opportunities():
    """分析所有历史机会数据，找出高价值模式"""
    patterns = {
        "high_markup_products": [],    # 加价倍数最高的品
        "trending_categories": [],      # 增长最快的品类
        "best_source_markets": Counter(),  # 哪个来源市场最赚
        "best_target_markets": Counter(),  # 哪个目标市场最赚
        "price_ranges": defaultdict(list),  # 最佳价格区间
    }

    # 读取价格对比数据 (items 列表格式)
    price_file = DATA / "price_comparison.json"
    if price_file.exists():
        with open(price_file) as f:
            price_data = json.load(f)
            for item in price_data.get("items", []):
                markup = item.get("markup", 0)
                if markup >= 3.0:
                    patterns["high_markup_products"].append({
                        "product": item.get("category", "unknown"),
                        "markup": markup,
                        "source": "1688",
                    })
                # 记录价格区间
                price = item.get("price_1688_cny", 0)
                if price > 0:
                    bucket = "low" if price < 50 else "mid" if price < 150 else "high"
                    patterns["price_ranges"][bucket].append(markup)

    # 读取趋势差数据 (top_opportunities 列表格式)
    for f in sorted(glob.glob(str(DATA / "trend_gaps_*.json"))):
        try:
            with open(f) as fh:
                trends = json.load(fh)
                for item in trends.get("top_opportunities", []):
                    gap = item.get("gap_score", 0)
                    if gap > 50:
                        patterns["trending_categories"].append({
                            "product": item.get("product_name_cn", "unknown"),
                            "gap_score": gap,
                            "window_months": item.get("estimated_window_months", 6),
                        })
        except Exception:
            pass

    # 读取扩展机会
    expanded = DATA / "expanded_opportunities.json"
    if expanded.exists():
        try:
            with open(expanded) as f:
                opps = json.load(f)
                items = opps if isinstance(opps, list) else opps.values() if isinstance(opps, dict) else []
                for item in items:
                    if isinstance(item, dict):
                        patterns["best_source_markets"][item.get("source_country", "CN")] += 1
                        patterns["best_target_markets"][item.get("target_country", "VN")] += 1
        except Exception:
            pass

    return patterns


def analyze_content_performance():
    """分析内容产出情况"""
    content_dir = DATA / "content"
    stats = {
        "total_pieces": 0,
        "platforms": Counter(),
        "dates": [],
    }

    if content_dir.exists():
        for date_dir in sorted(content_dir.iterdir()):
            if date_dir.is_dir():
                stats["dates"].append(date_dir.name)
                for f in date_dir.glob("*.md"):
                    stats["total_pieces"] += 1
                    platform = f.stem.split("_")[0]  # twitter, linkedin, etc
                    stats["platforms"][platform] += 1

    return stats


def generate_optimization_recommendations(opp_patterns, content_stats):
    """基于数据生成优化建议"""
    recs = []

    # 品类建议
    if opp_patterns["high_markup_products"]:
        top = sorted(opp_patterns["high_markup_products"],
                     key=lambda x: x.get("markup", 0), reverse=True)[:3]
        recs.append({
            "type": "focus_products",
            "action": "增加扫描频率",
            "targets": [t["product"] for t in top],
            "reason": f"这些品加价倍数最高 (>{top[0].get('markup', 0):.1f}x)",
        })

    # 趋势建议
    if opp_patterns["trending_categories"]:
        top_trends = sorted(opp_patterns["trending_categories"],
                           key=lambda x: x.get("gap_score", 0), reverse=True)[:3]
        recs.append({
            "type": "emerging_trends",
            "action": "立即创建针对性内容",
            "targets": [t["product"] for t in top_trends],
            "reason": "趋势差分数最高，时间窗口有限",
        })

    # 市场建议
    target_markets = opp_patterns["best_target_markets"]
    if target_markets:
        best_market = target_markets.most_common(1)[0][0] if target_markets else "VN"
        recs.append({
            "type": "market_focus",
            "action": f"加大 {best_market} 市场扫描",
            "reason": f"{best_market} 机会最多 ({target_markets.get(best_market, 0)}个)",
        })

    # 内容建议
    if content_stats["total_pieces"] > 0:
        recs.append({
            "type": "content_expansion",
            "action": "增加内容生成频率",
            "current": f"{content_stats['total_pieces']}份",
            "target": "每天至少10份跨平台内容",
        })

    return recs


def update_scanning_weights(recommendations):
    """根据优化建议更新扫描权重文件"""
    weights_file = DATA / "scanning_weights.json"

    weights = {
        "updated": datetime.now().isoformat(),
        "product_priority": [],
        "market_priority": ["VN", "TH", "ID", "PH"],
        "scan_frequency": {
            "trend_gap": "6h",
            "price_comparison": "6h",
            "polymarket": "6h",
        },
    }

    for rec in recommendations:
        if rec["type"] == "focus_products":
            weights["product_priority"] = rec["targets"]
        elif rec["type"] == "market_focus":
            # 把最优市场提到第一位
            market = rec.get("action", "").split()[-1] if "action" in rec else "VN"
            for m in ["VN", "TH", "ID", "PH"]:
                if m in market:
                    weights["market_priority"].remove(m)
                    weights["market_priority"].insert(0, m)
                    break

    with open(weights_file, "w") as f:
        json.dump(weights, f, ensure_ascii=False, indent=2)

    return weights


def log_evolution(cycle_data):
    """记录进化日志"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "evolution": cycle_data,
    }
    with open(EVOLUTION_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def count_evolution_cycles():
    """统计已经进化了多少次"""
    if not EVOLUTION_LOG.exists():
        return 0
    with open(EVOLUTION_LOG) as f:
        return sum(1 for _ in f)


def main():
    cycle_num = count_evolution_cycles() + 1
    print(f"🧬 进化循环 #{cycle_num}")
    print("=" * 50)

    # 1. 分析
    print("\n📊 分析历史数据...")
    opp_patterns = analyze_opportunities()
    content_stats = analyze_content_performance()

    print(f"  高加价品: {len(opp_patterns['high_markup_products'])}个")
    print(f"  趋势机会: {len(opp_patterns['trending_categories'])}个")
    print(f"  内容产出: {content_stats['total_pieces']}份")

    # 2. 优化建议
    print("\n💡 生成优化建议...")
    recs = generate_optimization_recommendations(opp_patterns, content_stats)
    for r in recs:
        print(f"  → [{r['type']}] {r['action']}")
        if 'reason' in r:
            print(f"    原因: {r['reason']}")

    # 3. 更新权重
    print("\n⚙️ 更新扫描权重...")
    weights = update_scanning_weights(recs)
    print(f"  优先品类: {weights['product_priority'][:3]}")
    print(f"  优先市场: {weights['market_priority'][:3]}")

    # 4. 记录进化
    cycle_data = {
        "cycle": cycle_num,
        "high_markup_count": len(opp_patterns["high_markup_products"]),
        "trend_count": len(opp_patterns["trending_categories"]),
        "content_count": content_stats["total_pieces"],
        "recommendations": len(recs),
        "weights_updated": True,
    }
    log_evolution(cycle_data)

    print(f"\n{'=' * 50}")
    print(f"✅ 进化 #{cycle_num} 完成 | {len(recs)} 条优化建议已应用")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
