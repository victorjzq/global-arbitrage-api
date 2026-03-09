#!/usr/bin/env python3
"""
每日信息差扫描器 — 用 Web Search 而非爬虫
每天跑一次，输出可执行的信息差机会

用法：python3 daily_scan.py
或 cron: 0 6 * * * cd ~/cowork-brain/projects/global-arbitrage && python3 src/daily_scan.py
"""

import sys, os, json, subprocess, re
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

DATA_DIR = os.path.expanduser("~/cowork-brain/projects/global-arbitrage/data")
REPORT_DIR = os.path.join(DATA_DIR, "daily_reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def ai_analyze(prompt, model="claude"):
    """调用 AI CLI 分析信息差"""
    try:
        if model == "claude":
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True, text=True, timeout=120
            )
        elif model == "grok":
            # grok 用 API
            import urllib.request, urllib.parse
            api_key = os.environ.get("XAI_API_KEY", "")
            if not api_key:
                return "Grok API key not set"
            data = json.dumps({
                "model": "grok-3-mini-fast",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000,
            }).encode()
            req = urllib.request.Request(
                "https://api.x.ai/v1/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result_json = json.loads(resp.read())
                return result_json["choices"][0]["message"]["content"]
        else:
            result = subprocess.run(
                [model, "-p", prompt] if model in ("gemini",) else ["gpt", prompt],
                capture_output=True, text=True, timeout=120
            )

        return result.stdout.strip() if hasattr(result, 'stdout') else str(result)
    except Exception as e:
        return f"AI分析失败: {e}"


def scan_price_gaps():
    """扫描价格信息差 — 用 AI 分析"""
    print("\n💰 [价格信息差] 扫描中...")

    categories = [
        ("美容仪器", "máy làm đẹp", "Beauty devices"),
        ("太阳能摄像头", "camera năng lượng mặt trời", "Solar cameras"),
        ("儿童编程机器人", "robot lập trình cho trẻ em", "Kids coding robots"),
        ("智能插座", "ổ cắm thông minh", "Smart plugs"),
        ("迷你投影仪", "máy chiếu mini", "Mini projectors"),
        ("宠物GPS追踪器", "GPS theo dõi thú cưng", "Pet GPS trackers"),
        ("折叠键盘", "bàn phím gấp", "Foldable keyboards"),
        ("便携式咖啡机", "máy pha cà phê di động", "Portable coffee makers"),
    ]

    results = []
    for cn, vn, en in categories:
        # 估算价格（基于已知数据）
        # 真实版本应该调 API 获取实时价格
        results.append({
            "keyword_cn": cn,
            "keyword_vn": vn,
            "keyword_en": en,
            "status": "need_price_check",
        })

    return results


def scan_trend_gaps():
    """扫描趋势时间差"""
    print("\n📈 [趋势时间差] 扫描中...")

    prompt = """列出5个中国2026年3月最火的消费品趋势，但越南市场还没有普及的。
格式：
1. [品类]: 中国热度(高/中) → 越南状态(空白/刚起步/已有) | 预估利润空间 | 行动建议
只列5个最有价值的，不要解释。"""

    result = ai_analyze(prompt)
    print(f"  AI 分析结果:\n{result}")
    return result


def scan_tool_gaps():
    """扫描工具/SaaS信息差"""
    print("\n🔧 [工具信息差] 扫描中...")

    prompt = """列出5个在美国/中国很流行但在越南/东南亚还没有的工具或App。
格式：
1. [工具名] (来源国): 功能简述 | 越南市场空白原因 | 本地化机会
只列5个最有商业价值的。"""

    result = ai_analyze(prompt)
    print(f"  AI 分析结果:\n{result}")
    return result


def scan_content_gaps():
    """扫描内容/知识信息差"""
    print("\n📚 [知识信息差] 扫描中...")

    prompt = """列出3个中文互联网有大量优质内容但越南语互联网几乎空白的领域。
格式：
1. [领域]: 中文资源量 vs 越南语资源量 | 变现方式 | 难度
"""

    result = ai_analyze(prompt)
    print(f"  AI 分析结果:\n{result}")
    return result


def generate_daily_report(price_gaps, trend_gaps, tool_gaps, content_gaps):
    """生成每日报告"""
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(REPORT_DIR, f"{today}.md")

    md = f"""# 每日信息差报告 — {today}

## 💰 价格信息差（待验证品类）

| 品类 | 中文关键词 | 越南关键词 | 状态 |
|------|----------|----------|------|
"""
    for p in price_gaps:
        md += f"| {p['keyword_en']} | {p['keyword_cn']} | {p['keyword_vn']} | {p['status']} |\n"

    md += f"""
## 📈 趋势时间差

{trend_gaps}

## 🔧 工具/SaaS 信息差

{tool_gaps}

## 📚 知识/内容信息差

{content_gaps}

---
*报告由 AI 信息差扫描器自动生成*
*下一步：选择 Top 3 机会，验证可行性，执行变现*
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f"\n📊 报告已保存: {report_path}")
    return report_path


def main():
    print(f"🌍 每日信息差扫描 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    price_gaps = scan_price_gaps()
    trend_gaps = scan_trend_gaps()
    tool_gaps = scan_tool_gaps()
    content_gaps = scan_content_gaps()

    report = generate_daily_report(price_gaps, trend_gaps, tool_gaps, content_gaps)

    print(f"\n✅ 扫描完成！报告: {report}")
    print("\n🎯 建议下一步：")
    print("  1. 选 Top 3 高利润品类")
    print("  2. 用 Playwright 获取实际价格")
    print("  3. 上架到 Shopee/FB/TikTok")


if __name__ == "__main__":
    main()
