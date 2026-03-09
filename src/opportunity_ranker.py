#!/usr/bin/env python3
"""
机会排序器 — 对所有扫描器发现的机会统一评分、去重、排序
输出 Top 10 可执行机会 + 具体下一步

评分公式: score = ROI_potential × confidence × urgency
"""

import json
import hashlib
from datetime import datetime
from typing import Optional


def normalize(value: float, min_v: float, max_v: float) -> float:
    """归一化到 0-1"""
    if max_v <= min_v:
        return 0.5
    return max(0, min(1, (value - min_v) / (max_v - min_v)))


def parse_markup(markup_str) -> float:
    """解析加价倍数，支持 '3-5x' / 3.0 / '2x' 等格式"""
    if isinstance(markup_str, (int, float)):
        return float(markup_str)
    s = str(markup_str).lower().replace('x', '').strip()
    if '-' in s:
        parts = s.split('-')
        try:
            return (float(parts[0]) + float(parts[1])) / 2
        except (ValueError, IndexError):
            return 1.0
    try:
        return float(s)
    except ValueError:
        return 1.0


def dedup_key(opp: dict) -> str:
    """生成去重 key：基于品类关键词"""
    raw = ''.join([
        opp.get('keyword_cn', opp.get('cn', opp.get('category', ''))),
        opp.get('keyword_vn', opp.get('vn', '')),
    ]).lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def estimate_roi(opp: dict) -> float:
    """估算 ROI 潜力 (0-10)"""
    markup = parse_markup(opp.get('markup', opp.get('profit_margin', 1)))

    # markup 是售价/成本比，转换为 ROI
    if 'profit_margin' in opp and isinstance(opp['profit_margin'], (int, float)):
        # profit_margin 是百分比
        roi_raw = opp['profit_margin'] / 100.0
    else:
        # markup = 售价/成本，ROI = markup - 1
        roi_raw = markup - 1

    # 映射到 0-10 分：ROI 0% → 0, ROI 200%+ → 10
    return min(10, max(0, roi_raw * 5))


def estimate_confidence(opp: dict) -> float:
    """估算置信度 (0-1)"""
    score = 0.5  # 基线

    # 有实际价格数据 → 高置信
    if opp.get('price_1688_cny') and opp.get('price_shopee_vnd'):
        score += 0.3
    elif opp.get('cn_price_range') or opp.get('sea_price_range'):
        score += 0.15

    # 有增长数据
    growth = opp.get('growth', '')
    if 'YoY' in str(growth) or '%' in str(growth):
        score += 0.1

    # verdict 包含 HIGH
    verdict = opp.get('verdict', '')
    if 'HIGH' in str(verdict).upper():
        score += 0.1
    elif 'MEDIUM' in str(verdict).upper():
        score += 0.05

    # 有来源 URL
    if opp.get('source_url'):
        score += 0.05

    return min(1.0, score)


def estimate_urgency(opp: dict) -> float:
    """估算紧迫度 (0-1): 季节性、增长速度、竞争窗口"""
    score = 0.5

    growth = str(opp.get('growth', ''))

    # 高增长 → 高紧迫（窗口期有限）
    if '+' in growth:
        try:
            pct = float(growth.split('+')[1].split('%')[0])
            if pct > 200:
                score += 0.3
            elif pct > 100:
                score += 0.2
            elif pct > 50:
                score += 0.1
        except (ValueError, IndexError):
            score += 0.1

    # 季节性关键词
    seasonal_kw = ['seasonal', 'peak', '季节', '夏', '冬', 'sun', 'chống nắng']
    for kw in seasonal_kw:
        if kw in str(opp).lower():
            score += 0.15
            break

    # 新兴市场
    emerging_kw = ['emerging', 'boom', 'growing', '空白', '刚起步']
    for kw in emerging_kw:
        if kw in str(opp).lower():
            score += 0.1
            break

    # 饱和市场 → 降低紧迫度
    if 'saturated' in str(opp).lower():
        score -= 0.2

    return max(0, min(1.0, score))


def generate_next_steps(opp: dict) -> list[str]:
    """为每个机会生成具体可执行的下一步"""
    steps = []
    category = opp.get('keyword_cn', opp.get('cn', opp.get('category', '')))
    vn_kw = opp.get('keyword_vn', opp.get('vn', ''))

    # Step 1: 验证价格
    if not opp.get('price_1688_cny'):
        steps.append(f"在 1688.com 搜索「{category}」确认实际采购价")
    if not opp.get('price_shopee_vnd'):
        steps.append(f"在 Shopee VN 搜索「{vn_kw}」确认市场售价和竞品数量")

    # Step 2: 小批量测试
    steps.append(f"1688 下单 5-10 件样品，预计成本 ¥{opp.get('price_1688_cny', '50-150')}")

    # Step 3: 上架
    steps.append(f"上架 Shopee VN/TikTok Shop，关键词: {vn_kw}")

    # Step 4: 投流测试
    steps.append("TikTok 短视频测试 3 条，预算 500k VND/条")

    return steps[:4]  # 最多 4 步


def rank_opportunities(
    opportunities: list[dict],
    top_n: int = 10,
    min_score: float = 1.0,
) -> list[dict]:
    """
    主函数：对所有机会评分、去重、排序

    Args:
        opportunities: 来自各扫描器的原始机会列表
        top_n: 返回前 N 个
        min_score: 最低分数阈值

    Returns:
        排序后的 top N 机会，附带评分和下一步
    """
    # 1. 去重
    seen = {}
    unique = []
    for opp in opportunities:
        key = dedup_key(opp)
        if key not in seen:
            seen[key] = True
            unique.append(opp)

    # 2. 评分
    scored = []
    for opp in unique:
        roi = estimate_roi(opp)
        confidence = estimate_confidence(opp)
        urgency = estimate_urgency(opp)

        # 综合分 = ROI × 置信度 × 紧迫度
        composite = roi * confidence * urgency
        next_steps = generate_next_steps(opp)

        scored.append({
            **opp,
            'scores': {
                'roi_potential': round(roi, 2),
                'confidence': round(confidence, 2),
                'urgency': round(urgency, 2),
                'composite': round(composite, 2),
            },
            'next_steps': next_steps,
            '_dedup_key': key,
        })

    # 3. 过滤 + 排序
    filtered = [s for s in scored if s['scores']['composite'] >= min_score]
    filtered.sort(key=lambda x: x['scores']['composite'], reverse=True)

    return filtered[:top_n]


def format_ranked_report(ranked: list[dict]) -> str:
    """格式化排序结果为可读报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f"# Top {len(ranked)} Actionable Opportunities",
        f"Generated: {now}",
        f"Scoring: ROI potential x confidence x urgency",
        "",
    ]

    for i, opp in enumerate(ranked, 1):
        s = opp['scores']
        name = opp.get('keyword_cn', opp.get('cn', opp.get('category', 'Unknown')))
        vn = opp.get('keyword_vn', opp.get('vn', ''))
        markup = opp.get('markup', opp.get('profit_margin', '?'))
        verdict = opp.get('verdict', '')

        lines.append(f"## #{i}. {name} → {vn}")
        lines.append(f"Score: {s['composite']:.1f} (ROI:{s['roi_potential']:.1f} Conf:{s['confidence']:.1f} Urg:{s['urgency']:.1f})")
        lines.append(f"Markup: {markup} | {verdict}")
        lines.append("")
        lines.append("Next steps:")
        for j, step in enumerate(opp.get('next_steps', []), 1):
            lines.append(f"  {j}. {step}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return '\n'.join(lines)


def format_telegram(ranked: list[dict]) -> str:
    """格式化为 Telegram 消息（纯文本，适合发送）"""
    now = datetime.now().strftime('%Y-%m-%d')
    lines = [f"[Daily Arbitrage] {now} Top {len(ranked)}", ""]

    for i, opp in enumerate(ranked, 1):
        s = opp['scores']
        name = opp.get('keyword_cn', opp.get('cn', opp.get('category', '')))
        markup = opp.get('markup', '?')
        verdict = opp.get('verdict', '').replace('🟢 ', '').replace('🟡 ', '').replace('🔴 ', '')
        lines.append(f"{i}. {name} | {markup} | {verdict} | score:{s['composite']:.1f}")

    lines.append("")
    lines.append("Details: ~/projects/global-arbitrage/data/daily/")
    return '\n'.join(lines)


# --- CLI ---
if __name__ == '__main__':
    import sys
    import os

    # 示例：从 arbitrage_api.py 的 ARBITRAGE_DB 加载
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # 尝试加载已有数据
    data_dir = os.path.expanduser("~/cowork-brain/projects/global-arbitrage/data")

    # 从 API 数据库加载
    from arbitrage_api import ARBITRAGE_DB
    opportunities = [{'category': k, **v} for k, v in ARBITRAGE_DB.items()]

    # 从最新的 price_comparison.json 加载
    price_file = os.path.join(data_dir, 'price_comparison.json')
    if os.path.exists(price_file):
        with open(price_file) as f:
            price_data = json.load(f)
            if isinstance(price_data, list):
                opportunities.extend(price_data)
            elif isinstance(price_data, dict) and 'opportunities' in price_data:
                opportunities.extend(price_data['opportunities'])

    ranked = rank_opportunities(opportunities)

    print(format_ranked_report(ranked))
    print("\n=== Telegram Format ===\n")
    print(format_telegram(ranked))
