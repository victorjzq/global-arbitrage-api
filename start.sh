#!/bin/bash
# 全球信息差系统 — 一键启动 7x24
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "🌍 启动全球信息差系统..."

# 1. 确保日志目录
mkdir -p data/logs data/daily data/content

# 2. 安装 cron 定时任务（每日06:00完整扫描）
if ! crontab -l 2>/dev/null | grep -q "daily_engine.py"; then
    # 每6小时扫描 + 每天06:00完整报告
    (crontab -l 2>/dev/null; echo "# Global Arbitrage System - 7x24") | crontab -
    (crontab -l 2>/dev/null; echo "0 6,12,18,0 * * * cd $DIR && python3 src/daily_engine.py >> data/logs/cron.log 2>&1 # ARBITRAGE_SCAN") | crontab -
    (crontab -l 2>/dev/null; echo "*/30 * * * * cd $DIR && python3 src/content_engine.py --auto >> data/logs/content.log 2>&1 # ARBITRAGE_CONTENT") | crontab -
    echo "✅ Cron 已安装（每6小时扫描 + 每30分钟内容生成）"
else
    echo "✅ Cron 已存在"
fi

# 3. PM2 启动常驻服务
pm2 start ecosystem.config.js 2>/dev/null || {
    echo "⚠️ PM2 启动失败，直接后台运行 API"
    nohup python3 src/api_server.py >> data/logs/api.log 2>&1 &
    echo "✅ API 后台启动 (PID: $!)"
}

# 4. 状态检查
echo ""
echo "📊 系统状态:"
python3 src/system_status.py

echo ""
echo "🔗 API: http://localhost:8899"
echo "📋 日志: $DIR/data/logs/"
echo "⏰ 扫描: 每6小时 (06:00/12:00/18:00/00:00)"
echo ""
echo "管理命令:"
echo "  pm2 status          — 查看进程"
echo "  pm2 logs            — 查看日志"
echo "  pm2 restart all     — 重启所有"
echo "  bash start.sh       — 重新启动"
echo "  python3 src/system_status.py  — 系统状态"
