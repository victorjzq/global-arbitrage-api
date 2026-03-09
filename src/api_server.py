#!/usr/bin/env python3
"""
7x24 API 服务 — pm2 管理的常驻进程
整合 arbitrage_api + 健康检查 + 自动重启
"""
import os
import sys
import json
import time
import signal
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arbitrage_api import ArbitrageHandler, HTTPServer

PORT = int(os.getenv("PORT", "8899"))
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "api.pid")

def write_pid():
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def cleanup(signum, frame):
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    write_pid()

    server = HTTPServer(("0.0.0.0", PORT), ArbitrageHandler)
    print(f"[{datetime.now().isoformat()}] API server on port {PORT}", flush=True)
    server.serve_forever()
