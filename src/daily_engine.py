#!/usr/bin/env python3
"""
每日自动化引擎 — 统一调度所有扫描器，生成聚合报告

流程:
1. 依次运行: trend_gap_scanner (daily_scan), arbitrage_scanner, polymarket_scanner
2. 聚合所有机会 → opportunity_ranker 排序
3. 保存到 data/daily/{date}.json
4. 生成 Telegram/Email 格式摘要
5. 记录执行指标

用法:
  python3 daily_engine.py              # 完整运行
  python3 daily_engine.py --dry-run    # 只打印，不保存
  python3 daily_engine.py --scanners trend,price  # 指定扫描器
"""

import sys
import os
import json
import time
import traceback
import subprocess
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

PROJECT_DIR = os.path.expanduser("~/cowork-brain/projects/global-arbitrage")
SRC_DIR = os.path.join(PROJECT_DIR, "src")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
LOG_DIR = os.path.join(DATA_DIR, "logs")

os.makedirs(DAILY_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

sys.path.insert(0, SRC_DIR)


class ExecutionMetrics:
    """跟踪执行指标"""

    def __init__(self):
        self.start_time = time.time()
        self.scanner_metrics = {}
        self.total_opportunities = 0
        self.total_estimated_value = 0
        self.errors = []

    def record_scanner(self, name: str, count: int, runtime: float, error: str = None):
        self.scanner_metrics[name] = {
            'opportunities_found': count,
            'runtime_seconds': round(runtime, 2),
            'status': 'error' if error else 'ok',
            'error': error,
        }
        if error:
            self.errors.append(f"{name}: {error}")

    def to_dict(self) -> dict:
        total_runtime = round(time.time() - self.start_time, 2)
        return {
            'total_runtime_seconds': total_runtime,
            'total_opportunities': self.total_opportunities,
            'total_estimated_value_usd': self.total_estimated_value,
            'scanners': self.scanner_metrics,
            'errors': self.errors,
            'success': len(self.errors) == 0,
        }


def run_trend_gap_scanner() -> list[dict]:
    """运行趋势信息差扫描 (daily_scan.py 的逻辑)"""
    print("[Engine] Running trend gap scanner...")

    opportunities = []

    try:
        from daily_scan import scan_price_gaps, ai_analyze
    except ImportError:
        print("  [WARN] daily_scan.py not importable, using built-in scan")
        from daily_scan import scan_price_gaps
        ai_analyze = None

    # 1. 价格品类扫描（不需要 AI）
    price_gaps = scan_price_gaps()
    for pg in price_gaps:
        pg['source'] = 'trend_gap_scanner'
        pg['scan_type'] = 'price_gap'
        opportunities.append(pg)

    # 2. AI 趋势分析（如果可用）
    if ai_analyze:
        try:
            trend_prompt = (
                "列出5个2026年3月中国最火的消费品趋势，但越南市场还没有普及的。"
                "返回 JSON 数组格式: [{\"category\": \"品类\", \"keyword_cn\": \"中文\", "
                "\"keyword_vn\": \"越南语\", \"markup\": \"3-5x\", \"verdict\": \"HIGH/MEDIUM\", "
                "\"growth\": \"增长描述\"}]。只返回 JSON，不要解释。"
            )
            result = ai_analyze(trend_prompt)

            # 尝试解析 JSON
            try:
                # 提取 JSON 部分
                json_start = result.find('[')
                json_end = result.rfind(']') + 1
                if json_start >= 0 and json_end > json_start:
                    trends = json.loads(result[json_start:json_end])
                    for t in trends:
                        t['source'] = 'trend_gap_scanner'
                        t['scan_type'] = 'ai_trend'
                        opportunities.append(t)
            except json.JSONDecodeError:
                # AI 返回非 JSON，存为文本机会
                opportunities.append({
                    'source': 'trend_gap_scanner',
                    'scan_type': 'ai_trend_text',
                    'raw_analysis': result[:500],
                    'category': 'ai_trend_analysis',
                })
        except Exception as e:
            print(f"  [WARN] AI trend analysis failed: {e}")

    return opportunities


def run_price_scanner() -> list[dict]:
    """运行价格对比扫描（从 arbitrage_api.py 加载已知数据）"""
    print("[Engine] Running price scanner...")

    opportunities = []

    try:
        from arbitrage_api import ARBITRAGE_DB
        for key, data in ARBITRAGE_DB.items():
            opp = {'category': key, **data, 'source': 'price_scanner'}
            opportunities.append(opp)
    except ImportError:
        print("  [WARN] arbitrage_api.py not importable")

    # 加载最新的 price_comparison.json
    price_file = os.path.join(DATA_DIR, 'price_comparison.json')
    if os.path.exists(price_file):
        try:
            with open(price_file) as f:
                price_data = json.load(f)
                items = price_data if isinstance(price_data, list) else price_data.get('opportunities', price_data.get('items', []))
                for item in items:
                    if isinstance(item, dict):
                        item['source'] = 'price_comparison'
                        opportunities.append(item)
        except (json.JSONDecodeError, Exception) as e:
            print(f"  [WARN] Failed to load price_comparison.json: {e}")

    return opportunities


def run_polymarket_scanner() -> list[dict]:
    """运行预测市场扫描器（如果存在）"""
    print("[Engine] Running polymarket scanner...")

    opportunities = []

    # 检查是否存在扫描器脚本
    scanner_paths = [
        os.path.join(SRC_DIR, 'prediction-markets', 'polymarket_scanner.py'),
        os.path.join(SRC_DIR, 'polymarket_scanner.py'),
    ]

    scanner_path = None
    for p in scanner_paths:
        if os.path.exists(p):
            scanner_path = p
            break

    if not scanner_path:
        print("  [INFO] No polymarket scanner found, skipping")
        return opportunities

    try:
        # 运行外部脚本，捕获 JSON 输出
        result = subprocess.run(
            [sys.executable, scanner_path, '--json'],
            capture_output=True, text=True, timeout=120,
            cwd=PROJECT_DIR,
        )
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout.strip())
                items = data if isinstance(data, list) else data.get('opportunities', [])
                for item in items:
                    if isinstance(item, dict):
                        item['source'] = 'polymarket_scanner'
                        opportunities.append(item)
            except json.JSONDecodeError:
                print(f"  [WARN] Polymarket output not JSON: {result.stdout[:200]}")
        if result.stderr:
            print(f"  [WARN] Polymarket stderr: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("  [WARN] Polymarket scanner timed out")
    except Exception as e:
        print(f"  [WARN] Polymarket scanner failed: {e}")

    return opportunities


def aggregate_and_rank(all_opportunities: list[dict]) -> list[dict]:
    """聚合所有机会并排序"""
    print(f"\n[Engine] Aggregating {len(all_opportunities)} raw opportunities...")

    from opportunity_ranker import rank_opportunities
    ranked = rank_opportunities(all_opportunities, top_n=10, min_score=0.0)

    print(f"[Engine] Ranked: {len(ranked)} opportunities after dedup and scoring")
    return ranked


def generate_daily_report(ranked: list[dict], metrics: dict, date_str: str) -> dict:
    """生成每日 JSON 报告"""
    report = {
        'date': date_str,
        'generated_at': datetime.now().isoformat(),
        'metrics': metrics,
        'top_opportunities': ranked,
        'summary': {
            'total_ranked': len(ranked),
            'avg_score': round(sum(o['scores']['composite'] for o in ranked) / max(len(ranked), 1), 2),
            'top_score': ranked[0]['scores']['composite'] if ranked else 0,
            'sources': list(set(o.get('source', 'unknown') for o in ranked)),
        },
    }
    return report


def format_telegram_summary(ranked: list[dict], metrics: dict, date_str: str) -> str:
    """生成 Telegram 格式摘要"""
    lines = [
        f"=== Daily Arbitrage Report {date_str} ===",
        f"Runtime: {metrics['total_runtime_seconds']}s | Found: {metrics['total_opportunities']}",
        "",
    ]

    for i, opp in enumerate(ranked[:5], 1):
        s = opp['scores']
        name = opp.get('keyword_cn', opp.get('cn', opp.get('category', '')))
        markup = opp.get('markup', '?')
        lines.append(
            f"{i}. {name} | {markup} | "
            f"score:{s['composite']:.1f} (ROI:{s['roi_potential']:.0f} C:{s['confidence']:.1f} U:{s['urgency']:.1f})"
        )

    if len(ranked) > 5:
        lines.append(f"... +{len(ranked) - 5} more")

    lines.extend([
        "",
        "Next steps for #1:",
    ])
    if ranked:
        for step in ranked[0].get('next_steps', [])[:3]:
            lines.append(f"  - {step}")

    if metrics.get('errors'):
        lines.extend(["", "Errors:"])
        for err in metrics['errors']:
            lines.append(f"  ! {err}")

    return '\n'.join(lines)


def format_email_summary(ranked: list[dict], metrics: dict, date_str: str) -> str:
    """生成 Email HTML 格式摘要"""
    html = f"""<html><body>
<h2>Daily Arbitrage Report - {date_str}</h2>
<p>Runtime: {metrics['total_runtime_seconds']}s | Opportunities: {metrics['total_opportunities']}</p>

<table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse">
<tr style="background:#f0f0f0">
  <th>#</th><th>Category</th><th>Markup</th><th>Score</th><th>Verdict</th><th>Next Step</th>
</tr>
"""
    for i, opp in enumerate(ranked[:10], 1):
        s = opp['scores']
        name = opp.get('keyword_cn', opp.get('cn', opp.get('category', '')))
        markup = opp.get('markup', '?')
        verdict = opp.get('verdict', '')
        next_step = opp.get('next_steps', [''])[0] if opp.get('next_steps') else ''
        color = '#e6ffe6' if 'HIGH' in str(verdict).upper() else '#fff9e6' if 'MEDIUM' in str(verdict).upper() else '#fff'
        html += f"""<tr style="background:{color}">
  <td>{i}</td><td>{name}</td><td>{markup}</td>
  <td>{s['composite']:.1f}</td><td>{verdict}</td><td>{next_step}</td>
</tr>\n"""

    html += "</table></body></html>"
    return html


def save_report(report: dict, telegram_msg: str, email_html: str, date_str: str, dry_run: bool = False):
    """保存所有报告文件"""
    if dry_run:
        print("\n[DRY RUN] Would save to:")
        print(f"  {DAILY_DIR}/{date_str}.json")
        print(f"  {DAILY_DIR}/{date_str}_telegram.txt")
        print(f"  {DAILY_DIR}/{date_str}_email.html")
        return

    # JSON 报告
    json_path = os.path.join(DAILY_DIR, f"{date_str}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved: {json_path}")

    # Telegram 文本
    tg_path = os.path.join(DAILY_DIR, f"{date_str}_telegram.txt")
    with open(tg_path, 'w', encoding='utf-8') as f:
        f.write(telegram_msg)
    print(f"  Saved: {tg_path}")

    # Email HTML
    email_path = os.path.join(DAILY_DIR, f"{date_str}_email.html")
    with open(email_path, 'w', encoding='utf-8') as f:
        f.write(email_html)
    print(f"  Saved: {email_path}")


def save_log(metrics: dict, date_str: str):
    """追加执行日志"""
    log_path = os.path.join(LOG_DIR, "engine.jsonl")
    entry = {
        'date': date_str,
        'timestamp': datetime.now().isoformat(),
        **metrics,
    }
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
    print(f"  Log appended: {log_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Daily Arbitrage Engine')
    parser.add_argument('--dry-run', action='store_true', help='Print only, do not save')
    parser.add_argument('--scanners', type=str, default='all',
                        help='Comma-separated scanner list: trend,price,polymarket (default: all)')
    args = parser.parse_args()

    date_str = datetime.now().strftime('%Y-%m-%d')
    print(f"{'=' * 60}")
    print(f"Daily Arbitrage Engine - {date_str}")
    print(f"{'=' * 60}")

    metrics = ExecutionMetrics()
    all_opportunities = []

    # 扫描器注册表
    scanners = {
        'trend': ('Trend Gap Scanner', run_trend_gap_scanner),
        'price': ('Price Scanner', run_price_scanner),
        'polymarket': ('Polymarket Scanner', run_polymarket_scanner),
    }

    # 选择要运行的扫描器
    if args.scanners == 'all':
        active_scanners = list(scanners.keys())
    else:
        active_scanners = [s.strip() for s in args.scanners.split(',')]

    # 依次运行扫描器
    for key in active_scanners:
        if key not in scanners:
            print(f"[WARN] Unknown scanner: {key}, skipping")
            continue

        name, func = scanners[key]
        print(f"\n{'─' * 40}")
        t0 = time.time()
        try:
            results = func()
            runtime = time.time() - t0
            all_opportunities.extend(results)
            metrics.record_scanner(name, len(results), runtime)
            print(f"  [{name}] Found {len(results)} opportunities in {runtime:.1f}s")
        except Exception as e:
            runtime = time.time() - t0
            metrics.record_scanner(name, 0, runtime, error=str(e))
            print(f"  [{name}] ERROR: {e}")
            traceback.print_exc()

    # 聚合 & 排序
    print(f"\n{'─' * 40}")
    ranked = aggregate_and_rank(all_opportunities)

    # 生成报告
    metrics.total_opportunities = len(all_opportunities)
    metrics_dict = metrics.to_dict()

    report = generate_daily_report(ranked, metrics_dict, date_str)
    telegram_msg = format_telegram_summary(ranked, metrics_dict, date_str)
    email_html = format_email_summary(ranked, metrics_dict, date_str)

    # 输出摘要
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(telegram_msg)

    # 保存
    print(f"\n{'─' * 40}")
    save_report(report, telegram_msg, email_html, date_str, dry_run=args.dry_run)
    if not args.dry_run:
        save_log(metrics_dict, date_str)

    # 退出码
    if metrics.errors:
        print(f"\n[WARN] Completed with {len(metrics.errors)} error(s)")
        sys.exit(0)  # 部分失败仍视为成功
    else:
        print(f"\n[OK] All scanners completed successfully")


if __name__ == '__main__':
    main()
