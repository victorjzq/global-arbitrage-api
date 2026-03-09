#!/usr/bin/env python3
"""
信息差即服务 (Arbitrage-as-a-Service)
把信息差发现能力暴露为 API/Telegram Bot

指数增长点：
- 每个用户的查询 = 免费市场情报（数据飞轮）
- 用户越多 → 数据越准 → 更多用户
- 边际成本 ≈ 0（AI token only）
"""

import os
import json
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
QUERY_LOG = os.path.join(DATA_DIR, "user_queries.jsonl")

# 预计算的信息差数据库（每日更新）
# 路线：CN→VN, CN→TH, CN→ID, JP→SEA, KR→SEA
ARBITRAGE_DB = {
    # ===== CN → VN (原有) =====
    "beauty_devices": {
        "route": "CN→VN",
        "cn": "美容仪器/射频美容仪",
        "vn": "máy làm đẹp",
        "cn_price_range": "¥50-150",
        "sea_price_range": "500k-2M VND",
        "markup": "3-5x",
        "growth": "+194% YoY on Shopee VN",
        "verdict": "🟢 HIGH PROFIT",
        "source_url": "1688.com search: 射频美容仪",
    },
    "solar_cameras": {
        "route": "CN→VN",
        "cn": "太阳能WiFi摄像头",
        "vn": "camera năng lượng mặt trời",
        "cn_price_range": "¥80-150",
        "sea_price_range": "800k-3M VND",
        "markup": "2.5-4x",
        "growth": "+312% YoY on Shopee VN",
        "verdict": "🟢 HIGH PROFIT",
    },
    "coding_robots": {
        "route": "CN→VN",
        "cn": "儿童编程机器人",
        "vn": "robot lập trình cho trẻ em",
        "cn_price_range": "¥30-80",
        "sea_price_range": "400k-1.5M VND",
        "markup": "4-8x",
        "growth": "STEM education boom in VN",
        "verdict": "🟢 HIGH PROFIT",
    },
    "smart_plugs": {
        "route": "CN→VN",
        "cn": "智能插座+电量监控",
        "vn": "ổ cắm thông minh",
        "cn_price_range": "¥15-30",
        "sea_price_range": "200k-600k VND",
        "markup": "3-5x",
        "growth": "+241% YoY on Shopee VN",
        "verdict": "🟢 HIGH PROFIT",
    },
    "phone_cases": {
        "route": "CN→VN",
        "cn": "手机壳",
        "vn": "ốp lưng điện thoại",
        "cn_price_range": "¥2-15",
        "sea_price_range": "50k-200k VND",
        "markup": "3-10x",
        "growth": "Evergreen category",
        "verdict": "🟡 MEDIUM (saturated)",
    },
    "sun_protection": {
        "route": "CN→VN",
        "cn": "防晒衣/冰袖/防晒帽",
        "vn": "áo chống nắng / ống tay / nón",
        "cn_price_range": "¥10-30",
        "sea_price_range": "75k-265k VND",
        "markup": "2-4x",
        "growth": "Seasonal peak Mar-Sep",
        "verdict": "🟢 HIGH (seasonal)",
    },
    "mini_projectors": {
        "route": "CN→VN",
        "cn": "迷你投影仪",
        "vn": "máy chiếu mini",
        "cn_price_range": "¥100-300",
        "sea_price_range": "1.5M-5M VND",
        "markup": "2-3x",
        "growth": "+85% YoY",
        "verdict": "🟡 MEDIUM",
    },
    "pet_gps": {
        "route": "CN→VN",
        "cn": "宠物GPS追踪器",
        "vn": "GPS theo dõi thú cưng",
        "cn_price_range": "¥30-80",
        "sea_price_range": "300k-1M VND",
        "markup": "2-3x",
        "growth": "Pet economy growing 40% YoY in VN",
        "verdict": "🟢 HIGH (emerging)",
    },
    # ===== CN → TH (新增) =====
    "th_sun_protection": {
        "route": "CN→TH",
        "cn": "UPF50+防晒衣/冰袖",
        "vn": "เสื้อกันแดด UPF50+",
        "cn_price_range": "¥15-40",
        "sea_price_range": "฿199-599",
        "markup": "3-4x",
        "growth": "+95% during 9.9 campaign",
        "verdict": "🟢 HIGH PROFIT",
    },
    "th_smart_home": {
        "route": "CN→TH",
        "cn": "智能家居(语音控制电饭煲/空气净化器)",
        "vn": "สมาร์ทโฮม",
        "cn_price_range": "¥20-80",
        "sea_price_range": "฿299-999",
        "markup": "2.5-4x",
        "growth": "+68% conversion with Thai voice control",
        "verdict": "🟢 HIGH PROFIT",
    },
    "th_pet_care": {
        "route": "CN→TH",
        "cn": "宠物用品(散热垫/自动喂食器)",
        "vn": "สินค้าสัตว์เลี้ยง",
        "cn_price_range": "¥10-50",
        "sea_price_range": "฿159-699",
        "markup": "3-5x",
        "growth": "+33% pet ownership 2025",
        "verdict": "🟢 HIGH PROFIT",
    },
    "th_beauty_tools": {
        "route": "CN→TH",
        "cn": "LED面膜仪/美容仪",
        "vn": "เครื่องมือความงาม",
        "cn_price_range": "¥50-150",
        "sea_price_range": "฿599-2999",
        "markup": "3-5x",
        "growth": "BPC = 40-50% GMV on Shopee TH",
        "verdict": "🟢 HIGH PROFIT",
    },
    "th_fashion_accessories": {
        "route": "CN→TH",
        "cn": "时尚配饰(直播带货爆款)",
        "vn": "แฟชั่นเครื่องประดับ",
        "cn_price_range": "¥5-30",
        "sea_price_range": "฿99-499",
        "markup": "3-8x",
        "growth": "800x sales surge via live commerce",
        "verdict": "🟢 HIGH PROFIT",
    },
    # ===== CN → ID (新增) =====
    "id_modest_fashion": {
        "route": "CN→ID",
        "cn": "穆斯林时尚配饰(头巾扣/围巾)",
        "vn": "aksesori hijab",
        "cn_price_range": "¥8-35",
        "sea_price_range": "Rp 25k-150k",
        "markup": "2-4x",
        "growth": "Fashion = 16% of all transactions",
        "verdict": "🟢 HIGH PROFIT",
    },
    "id_home_storage": {
        "route": "CN→ID",
        "cn": "收纳用品/厨房小工具",
        "vn": "organizer rumah",
        "cn_price_range": "¥5-25",
        "sea_price_range": "Rp 20k-120k",
        "markup": "2.5-4x",
        "growth": "Home & Living top category 2025-2026",
        "verdict": "🟢 HIGH PROFIT",
    },
    "id_phone_accessories": {
        "route": "CN→ID",
        "cn": "手机配件/游戏外设",
        "vn": "aksesoris HP & gaming",
        "cn_price_range": "¥10-60",
        "sea_price_range": "Rp 50k-350k",
        "markup": "2-3x",
        "growth": "Refurbished electronics +29% GMV share",
        "verdict": "🟡 MEDIUM",
    },
    "id_smart_home": {
        "route": "CN→ID",
        "cn": "智能家居(印尼语语音控制)",
        "vn": "smart home Indonesia",
        "cn_price_range": "¥20-80",
        "sea_price_range": "Rp 80k-500k",
        "markup": "2.5-4x",
        "growth": "Smart home dominant 2026",
        "verdict": "🟢 HIGH PROFIT",
    },
    "id_health_snacks": {
        "route": "CN→ID",
        "cn": "功能性健康零食",
        "vn": "snack sehat",
        "cn_price_range": "¥8-30",
        "sea_price_range": "Rp 30k-150k",
        "markup": "2-3x",
        "growth": "Preventive health trend rising",
        "verdict": "🟡 MEDIUM",
    },
    # ===== JP → SEA (新增) =====
    "jp_snacks_th": {
        "route": "JP→TH",
        "cn": "日本零食(KitKat地域限定/抹茶/北海道牛乳)",
        "vn": "ขนมญี่ปุ่น",
        "cn_price_range": "¥400-700",
        "sea_price_range": "฿150-350",
        "markup": "1.5-2.5x",
        "growth": "Steady, JPY weakness boosts margins",
        "verdict": "🟢 HIGH (margin play)",
    },
    "jp_stationery": {
        "route": "JP→ID",
        "cn": "日本文具(Pilot/Zebra/Uni)",
        "vn": "alat tulis Jepang",
        "cn_price_range": "¥100-500/set",
        "sea_price_range": "Rp 30k-200k/item",
        "markup": "2-3x",
        "growth": "Student & office worker demand growing",
        "verdict": "🟡 MEDIUM",
    },
    "jp_beauty_devices": {
        "route": "JP→TH",
        "cn": "日本美容仪(ReFa/YA-MAN/Panasonic)",
        "vn": "เครื่องสำอางญี่ปุ่น",
        "cn_price_range": "¥2000-8000",
        "sea_price_range": "฿1500-6000",
        "markup": "1.5-2x",
        "growth": "Premium segment stable",
        "verdict": "🟡 MEDIUM (high ticket)",
    },
    "jp_appliances": {
        "route": "JP→VN",
        "cn": "日本小家电(象印/虎牌保温杯/电饭煲)",
        "vn": "đồ gia dụng Nhật",
        "cn_price_range": "¥3000-15000",
        "sea_price_range": "2M-10M VND",
        "markup": "1.5-2x",
        "growth": "Brand trust premium holds",
        "verdict": "🟡 MEDIUM (high ticket)",
    },
    # ===== KR → SEA (新增) =====
    "kr_skincare_th": {
        "route": "KR→TH",
        "cn": "韩国护肤(COSRX/Innisfree/VT)",
        "vn": "สกินแคร์เกาหลี",
        "cn_price_range": "$5-15",
        "sea_price_range": "฿250-750",
        "markup": "1.5-2.5x",
        "growth": "+10.5% CAGR, $1.1B TH market",
        "verdict": "🟢 HIGH PROFIT",
    },
    "kr_cosmetics_id": {
        "route": "KR→ID",
        "cn": "韩国美妆(精华/面膜)",
        "vn": "kosmetik Korea",
        "cn_price_range": "$3-12",
        "sea_price_range": "Rp 50k-200k",
        "markup": "1.5-2.5x",
        "growth": "+9.6% CAGR, Shopee=73% beauty sales",
        "verdict": "🟢 HIGH PROFIT",
    },
    "kr_skincare_vn": {
        "route": "KR→VN",
        "cn": "韩国护肤品(VN市场)",
        "vn": "mỹ phẩm Hàn Quốc",
        "cn_price_range": "$5-15",
        "sea_price_range": "200k-600k VND",
        "markup": "1.5-2x",
        "growth": "+9.6% CAGR",
        "verdict": "🟢 HIGH PROFIT",
    },
    "kr_color_cosmetics_th": {
        "route": "KR→TH",
        "cn": "韩国彩妆(ROM&ND/Etude唇釉/气垫)",
        "vn": "เครื่องสำอางเกาหลี",
        "cn_price_range": "$3-10",
        "sea_price_range": "฿199-499",
        "markup": "2-3x",
        "growth": "Female 67.4% of market, high repurchase",
        "verdict": "🟢 HIGH PROFIT",
    },
}


def log_query(query, source="api"):
    """记录用户查询 — 这就是数据飞轮"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "source": source,
    }
    with open(QUERY_LOG, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def search_arbitrage(query, route_filter=None):
    """搜索信息差机会
    query: 关键词搜索
    route_filter: 可选，如 "CN→TH", "KR→ID" 等筛选路线
    """
    query_lower = query.lower()
    results = []

    for key, data in ARBITRAGE_DB.items():
        # 路线过滤
        if route_filter and data.get("route", "") != route_filter:
            continue
        # 关键词匹配（搜索中文名、本地名、key、路线）
        searchable = f"{data['cn']} {data['vn']} {key} {data.get('route', '')}".lower()
        if any(word in searchable for word in query_lower.split()):
            results.append({"category": key, **data})

    if not results:
        # 如果有路线过滤但没匹配，返回该路线所有高利润
        if route_filter:
            results = [{"category": k, **v} for k, v in ARBITRAGE_DB.items()
                       if "HIGH" in v.get("verdict", "") and v.get("route", "") == route_filter]
        else:
            # 返回所有高利润机会
            results = [{"category": k, **v} for k, v in ARBITRAGE_DB.items() if "HIGH" in v.get("verdict", "")]

    return results


def format_response(results, query):
    """格式化响应"""
    if not results:
        return {"status": "no_results", "message": f"No arbitrage data found for '{query}'. Try: beauty, cameras, robots, phones, sun protection"}

    formatted = []
    for r in results:
        formatted.append({
            "route": r.get("route", "CN→VN"),
            "category": r["category"],
            "source_keyword": r["cn"],
            "target_keyword": r["vn"],
            "source_price": r["cn_price_range"],
            "target_price": r["sea_price_range"],
            "markup": r["markup"],
            "growth": r["growth"],
            "verdict": r["verdict"],
        })

    return {
        "status": "ok",
        "query": query,
        "results": formatted,
        "count": len(formatted),
        "updated": "2026-03-09",
        "note": "Subscribe for daily updates: t.me/global_arbitrage_bot",
    }


class ArbitrageHandler(BaseHTTPRequestHandler):
    """简单 HTTP API"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/search":
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            route = params.get("route", [None])[0]
            log_query(f"{query} [route={route}]", "api")
            results = search_arbitrage(query, route_filter=route)
            response = format_response(results, query)

        elif parsed.path == "/api/top":
            params = urllib.parse.parse_qs(parsed.query)
            route = params.get("route", [None])[0]
            log_query(f"top_opportunities [route={route}]", "api")
            results = [{"category": k, **v} for k, v in ARBITRAGE_DB.items()
                       if "HIGH" in v.get("verdict", "") and (not route or v.get("route") == route)]
            response = format_response(results, "top opportunities")

        elif parsed.path == "/api/routes":
            # 列出所有可用路线
            routes = {}
            for k, v in ARBITRAGE_DB.items():
                r = v.get("route", "unknown")
                if r not in routes:
                    routes[r] = {"count": 0, "high_profit": 0}
                routes[r]["count"] += 1
                if "HIGH" in v.get("verdict", ""):
                    routes[r]["high_profit"] += 1
            response = {"routes": routes, "total_categories": len(ARBITRAGE_DB)}

        elif parsed.path == "/api/stats":
            # 有多少查询（数据飞轮指标）
            count = 0
            if os.path.exists(QUERY_LOG):
                with open(QUERY_LOG) as f:
                    count = sum(1 for _ in f)
            routes = set(v.get("route", "") for v in ARBITRAGE_DB.values())
            response = {"total_queries": count, "categories": len(ARBITRAGE_DB), "routes": sorted(routes)}

        else:
            response = {
                "service": "Global Arbitrage API",
                "endpoints": {
                    "/api/search?q=keyword&route=CN→TH": "Search arbitrage opportunities (route optional)",
                    "/api/top?route=CN→TH": "Top high-profit opportunities (route optional)",
                    "/api/routes": "List all available trade routes",
                    "/api/stats": "Usage statistics",
                },
                "version": "0.2.0",
                "routes": ["CN→VN", "CN→TH", "CN→ID", "JP→TH", "JP→ID", "JP→VN", "KR→TH", "KR→ID", "KR→VN"],
            }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode())

    def log_message(self, format, *args):
        pass  # 静默日志


def run_server(port=8899):
    """启动 API 服务"""
    server = HTTPServer(("0.0.0.0", port), ArbitrageHandler)
    print(f"🌍 Arbitrage API running on http://localhost:{port}")
    print(f"  GET /api/search?q=beauty  — 搜索信息差")
    print(f"  GET /api/top             — 高利润机会")
    print(f"  GET /api/stats           — 使用统计")
    server.serve_forever()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    run_server(port)
