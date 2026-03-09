#!/usr/bin/env python3
"""
全球信息差扫描器 v1
自动发现跨市场的信息不对称机会

信息差来源：
1. 中国电商热搜 vs 越南市场空白
2. TikTok 全球热门 vs 本地缺失
3. 价格差异扫描（1688 vs Shopee）
4. Google Trends 跨区域对比
"""

import sys, os, json, time, re
from datetime import datetime
sys.stdout.reconfigure(line_buffering=True)

DATA_DIR = os.path.expanduser("~/cowork-brain/projects/global-arbitrage/data")
os.makedirs(DATA_DIR, exist_ok=True)


class ArbitrageScanner:
    """信息差机会扫描器"""

    def __init__(self):
        self.opportunities = []
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    def scan_1688_trending(self, page):
        """扫描1688热搜/热卖，找到中国正在爆的品"""
        print("\n🔍 [1688] 扫描热搜趋势...")
        try:
            page.goto("https://www.1688.com/", timeout=20000, wait_until="domcontentloaded")
            time.sleep(3)

            # 提取热搜词
            hot_searches = page.evaluate("""() => {
                const keywords = [];
                // 热搜区域
                const hotEls = document.querySelectorAll('[class*="hot"] a, [class*="trend"] a, [class*="rank"] a');
                hotEls.forEach(el => {
                    const text = el.innerText.trim();
                    if (text && text.length > 1 && text.length < 30) {
                        keywords.push(text);
                    }
                });
                return [...new Set(keywords)].slice(0, 30);
            }""")

            if not hot_searches:
                # 备选：搜索框推荐
                hot_searches = page.evaluate("""() => {
                    const els = document.querySelectorAll('a[href*="keywords"], a[href*="search"]');
                    return Array.from(els).map(el => el.innerText.trim()).filter(t => t.length > 1 && t.length < 30).slice(0, 20);
                }""")

            print(f"  找到 {len(hot_searches)} 个热搜词")
            for kw in hot_searches[:10]:
                print(f"    🔥 {kw}")

            return hot_searches

        except Exception as e:
            print(f"  ❌ 1688扫描失败: {e}")
            return []

    def scan_tiktok_creative_center(self, page):
        """扫描 TikTok Creative Center 热门商品/素材"""
        print("\n🔍 [TikTok] 扫描热门趋势...")
        try:
            page.goto("https://ads.tiktok.com/business/creativecenter/inspiration/popular/pc/en", timeout=20000)
            time.sleep(5)

            trends = page.evaluate("""() => {
                const items = [];
                document.querySelectorAll('[class*="trend"], [class*="card"], [class*="item"]').forEach(el => {
                    const text = el.innerText.trim();
                    if (text && text.length > 5 && text.length < 100) {
                        items.push(text.split('\\n')[0]);
                    }
                });
                return [...new Set(items)].slice(0, 20);
            }""")

            print(f"  找到 {len(trends)} 个热门趋势")
            for t in trends[:10]:
                print(f"    📈 {t}")

            return trends

        except Exception as e:
            print(f"  ❌ TikTok扫描失败: {e}")
            return []

    def scan_shopee_vn_trending(self, page):
        """扫描 Shopee 越南热搜，看当前市场需求"""
        print("\n🔍 [Shopee VN] 扫描热搜...")
        try:
            page.goto("https://shopee.vn/", timeout=20000, wait_until="domcontentloaded")
            time.sleep(3)

            trends = page.evaluate("""() => {
                const items = [];
                // 热搜关键词
                document.querySelectorAll('[class*="trending"] a, [class*="search-trending"] a, a[href*="search"]').forEach(el => {
                    const text = el.innerText.trim();
                    if (text && text.length > 1 && text.length < 50) {
                        items.push(text);
                    }
                });
                return [...new Set(items)].slice(0, 30);
            }""")

            print(f"  找到 {len(trends)} 个Shopee热搜")
            for t in trends[:10]:
                print(f"    🛒 {t}")

            return trends

        except Exception as e:
            print(f"  ❌ Shopee扫描失败: {e}")
            return []

    def compare_price(self, page, keyword_cn, keyword_vn=None):
        """对比同一商品在1688和Shopee的价格"""
        print(f"\n💰 价格对比: {keyword_cn}")

        # 1688 价格
        price_1688 = self._get_1688_price(page, keyword_cn)

        # Shopee 价格
        if not keyword_vn:
            keyword_vn = keyword_cn  # 需要翻译
        price_shopee = self._get_shopee_price(page, keyword_vn)

        if price_1688 and price_shopee:
            # 转换：1 CNY ≈ 3,500 VND
            cost_vnd = price_1688 * 3500
            markup = price_shopee / cost_vnd if cost_vnd > 0 else 0
            profit_margin = (price_shopee - cost_vnd) / price_shopee if price_shopee > 0 else 0

            opp = {
                "keyword_cn": keyword_cn,
                "keyword_vn": keyword_vn,
                "price_1688_cny": price_1688,
                "price_shopee_vnd": price_shopee,
                "cost_vnd": cost_vnd,
                "markup": round(markup, 1),
                "profit_margin": round(profit_margin * 100, 1),
                "score": round(markup * 10, 0),  # 简单评分
            }
            print(f"  1688: ¥{price_1688} → Shopee: {price_shopee:,.0f}₫")
            print(f"  加价倍数: {markup:.1f}x | 利润率: {profit_margin*100:.0f}%")

            if markup >= 2:
                opp["verdict"] = "🟢 高利润机会"
                self.opportunities.append(opp)
            elif markup >= 1.5:
                opp["verdict"] = "🟡 中等机会"
                self.opportunities.append(opp)
            else:
                opp["verdict"] = "🔴 利润不足"

            return opp

        return None

    def _get_1688_price(self, page, keyword):
        """获取1688最低价"""
        try:
            page.goto(f"https://s.1688.com/selloffer/offer_search.htm?keywords={keyword}", timeout=15000)
            time.sleep(3)
            prices = page.evaluate("""() => {
                const priceEls = document.querySelectorAll('[class*="price"], .sm-offer-priceNum');
                return Array.from(priceEls).map(el => {
                    const num = parseFloat(el.innerText.replace(/[^0-9.]/g, ''));
                    return isNaN(num) ? null : num;
                }).filter(n => n && n > 0.1 && n < 10000).slice(0, 10);
            }""")
            if prices:
                return min(prices)
        except:
            pass
        return None

    def _get_shopee_price(self, page, keyword):
        """获取Shopee越南平均价"""
        try:
            page.goto(f"https://shopee.vn/search?keyword={keyword}", timeout=15000)
            time.sleep(3)
            prices = page.evaluate("""() => {
                const priceEls = document.querySelectorAll('[class*="price"], ._1xk7ak');
                return Array.from(priceEls).map(el => {
                    const text = el.innerText.replace(/[^0-9]/g, '');
                    const num = parseInt(text);
                    return (num && num > 1000 && num < 100000000) ? num : null;
                }).filter(Boolean).slice(0, 10);
            }""")
            if prices:
                # 返回中位数
                prices.sort()
                return prices[len(prices) // 2]
        except:
            pass
        return None

    def find_gaps(self, cn_trends, vn_trends):
        """找到中国有但越南没有的趋势"""
        print("\n🔎 分析信息差（中国有 → 越南没有）...")

        # 简单关键词匹配
        vn_text = ' '.join(vn_trends).lower()
        gaps = []
        for trend in cn_trends:
            # 检查越南市场是否已有（简单匹配）
            # 真实场景需要翻译+语义匹配
            if trend.lower() not in vn_text:
                gaps.append(trend)

        print(f"  发现 {len(gaps)} 个潜在信息差:")
        for g in gaps[:10]:
            print(f"    🎯 {g}")

        return gaps

    def generate_report(self):
        """生成信息差报告"""
        report_path = os.path.join(DATA_DIR, f"arbitrage_report_{self.timestamp}.json")
        report = {
            "timestamp": self.timestamp,
            "opportunities": self.opportunities,
            "summary": {
                "total_scanned": len(self.opportunities),
                "high_profit": len([o for o in self.opportunities if o.get("markup", 0) >= 2]),
                "medium_profit": len([o for o in self.opportunities if 1.5 <= o.get("markup", 0) < 2]),
            }
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Markdown 报告
        md_path = os.path.join(DATA_DIR, f"arbitrage_report_{self.timestamp}.md")
        md = f"# 信息差扫描报告 — {self.timestamp}\n\n"
        md += f"## 概览\n"
        md += f"- 扫描机会数: {report['summary']['total_scanned']}\n"
        md += f"- 🟢 高利润: {report['summary']['high_profit']}\n"
        md += f"- 🟡 中等: {report['summary']['medium_profit']}\n\n"

        md += "## 机会列表\n\n"
        md += "| 商品 | 1688价 | Shopee价 | 加价 | 利润率 | 评估 |\n"
        md += "|------|--------|----------|------|--------|------|\n"
        for o in sorted(self.opportunities, key=lambda x: x.get("markup", 0), reverse=True):
            md += f"| {o['keyword_cn']} | ¥{o.get('price_1688_cny', '?')} | {o.get('price_shopee_vnd', '?'):,.0f}₫ | {o.get('markup', '?')}x | {o.get('profit_margin', '?')}% | {o.get('verdict', '')} |\n"

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md)

        print(f"\n📊 报告已保存:")
        print(f"  JSON: {report_path}")
        print(f"  MD:   {md_path}")

        return report


def main():
    from playwright.sync_api import sync_playwright

    scanner = ArbitrageScanner()

    print("🌍 全球信息差扫描器启动...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = ctx.new_page()

        # Step 1: 扫描中国趋势
        cn_trends = scanner.scan_1688_trending(page)

        # Step 2: 扫描越南市场
        vn_trends = scanner.scan_shopee_vn_trending(page)

        # Step 3: 发现信息差
        gaps = scanner.find_gaps(cn_trends, vn_trends)

        # Step 4: 对热门品做价格对比
        test_keywords = [
            ("防晒衣女", "áo chống nắng nữ"),
            ("手机壳", "ốp lưng điện thoại"),
            ("冰袖", "ống tay chống nắng"),
            ("迷你风扇", "quạt mini cầm tay"),
            ("车载手机支架", "giá đỡ điện thoại ô tô"),
            ("蓝牙耳机", "tai nghe bluetooth"),
            ("充电宝", "sạc dự phòng"),
            ("瑜伽裤", "quần tập yoga"),
        ]

        for cn, vn in test_keywords:
            scanner.compare_price(page, cn, vn)
            time.sleep(1)

        browser.close()

    # 生成报告
    report = scanner.generate_report()

    print(f"\n{'='*50}")
    print(f"✅ 扫描完成！发现 {len(scanner.opportunities)} 个信息差机会")


if __name__ == "__main__":
    main()
