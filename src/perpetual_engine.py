#!/usr/bin/env python3
"""
永续引擎 — 7x24 信息差捕获→内容生成→分发→数据回流
不需要人类介入的完整闭环。

每次运行:
1. 扫描新机会 (daily_engine)
2. 生成多平台内容 (content_engine)
3. 记录指标 (数据飞轮)
4. 自我进化 (根据数据调整策略)

由 cron 触发，每6小时运行一次。
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
DATA = PROJECT / "data"
LOGS = DATA / "logs"
METRICS_FILE = LOGS / "perpetual_metrics.jsonl"

os.makedirs(LOGS, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_script(name, script_path, args=None):
    """运行子脚本，返回成功与否"""
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    log(f"▶ {name}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd=str(PROJECT)
        )
        if result.returncode == 0:
            log(f"  ✅ {name} 完成")
            return True, result.stdout
        else:
            log(f"  ❌ {name} 失败: {result.stderr[:200]}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        log(f"  ⏰ {name} 超时")
        return False, "timeout"
    except Exception as e:
        log(f"  ❌ {name} 异常: {e}")
        return False, str(e)


def record_metrics(cycle_data):
    """记录每次循环的指标"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "cycle": cycle_data,
    }
    with open(METRICS_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def count_opportunities():
    """统计当前机会数"""
    today = datetime.now().strftime("%Y%m%d")
    patterns = [
        DATA / f"trend_gaps_{today}.json",
        DATA / "price_comparison.json",
        DATA / "polymarket_opportunities.json",
    ]
    total = 0
    for p in patterns:
        if p.exists():
            try:
                with open(p) as f:
                    d = json.load(f)
                    if isinstance(d, list):
                        total += len(d)
                    elif isinstance(d, dict):
                        # 计算所有值中的列表长度之和，或键数
                        list_vals = [v for v in d.values() if isinstance(v, list)]
                        if list_vals:
                            total += sum(len(v) for v in list_vals)
                        else:
                            total += len(d)
            except Exception:
                pass
    return total


def count_content():
    """统计生成的内容数"""
    content_dir = DATA / "content"
    if not content_dir.exists():
        return 0
    count = 0
    for d in content_dir.iterdir():
        if d.is_dir():
            count += len(list(d.glob("*.md")))
    return count


def main():
    log("=" * 50)
    log("🌍 永续引擎启动")
    log("=" * 50)

    cycle = {
        "start": datetime.now().isoformat(),
        "scanners": {},
        "content": {},
        "opportunities_found": 0,
        "content_pieces": 0,
    }

    # Phase 1: 扫描
    log("\n📡 Phase 1: 扫描信息差")

    scanners = [
        ("趋势差扫描", SRC / "trend_gap_scanner.py", None),
        ("价格差扫描", SRC / "daily_scan.py", None),
    ]

    # Polymarket 扫描器如果存在也加上
    pm_scanner = SRC / "prediction-markets" / "polymarket_scanner.py"
    if pm_scanner.exists():
        scanners.append(("预测市场扫描", pm_scanner, None))

    for name, path, args in scanners:
        if path.exists():
            ok, output = run_script(name, path, args)
            cycle["scanners"][name] = {"success": ok, "output_len": len(output)}

    cycle["opportunities_found"] = count_opportunities()
    log(f"\n  📊 发现 {cycle['opportunities_found']} 个机会")

    # Phase 2: 生成内容
    log("\n📝 Phase 2: 生成多平台内容")
    content_engine = SRC / "content_engine.py"
    if content_engine.exists():
        ok, output = run_script("内容引擎", content_engine)
        cycle["content"]["generated"] = ok

    cycle["content_pieces"] = count_content()
    log(f"  📄 累计 {cycle['content_pieces']} 份内容")

    # Phase 3: 报告生成
    log("\n📄 Phase 3: 更新报告")
    html_converter = SRC / "md_to_html.py"
    if html_converter.exists():
        run_script("HTML转换", html_converter)

    # Phase 4: 自动发布到 Substack
    log("\n📢 Phase 4: 发布到 Substack")
    substack_pub = SRC / "publish_substack.py"
    if substack_pub.exists():
        run_script("Substack发布", substack_pub)

    # Phase 5: 自我进化
    log("\n🧬 Phase 4: 自我进化")
    evolution = SRC / "evolution_loop.py"
    if evolution.exists():
        run_script("进化引擎", evolution)

    # Phase 5: 指标记录
    cycle["end"] = datetime.now().isoformat()
    cycle["runtime_seconds"] = (
        datetime.fromisoformat(cycle["end"]) - datetime.fromisoformat(cycle["start"])
    ).total_seconds()

    record_metrics(cycle)

    log(f"\n{'=' * 50}")
    log(f"✅ 循环完成 | 耗时 {cycle['runtime_seconds']:.0f}s")
    log(f"   机会: {cycle['opportunities_found']} | 内容: {cycle['content_pieces']}")
    log(f"{'=' * 50}")


if __name__ == "__main__":
    main()
