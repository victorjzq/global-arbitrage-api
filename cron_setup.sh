#!/bin/bash
# Daily Engine 定时任务 — macOS launchd
#
# 用法:
#   bash cron_setup.sh install    # 安装，每天 06:00 运行
#   bash cron_setup.sh uninstall  # 卸载
#   bash cron_setup.sh status     # 查看状态
#   bash cron_setup.sh run        # 立即手动运行

set -euo pipefail

LABEL="com.cowork.global-arbitrage.daily-engine"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
PROJECT_DIR="$HOME/cowork-brain/projects/global-arbitrage"
PYTHON="$(which python3)"
SCRIPT="${PROJECT_DIR}/src/daily_engine.py"
LOG_DIR="${PROJECT_DIR}/data/logs"
LOG_OUT="${LOG_DIR}/daily_engine.stdout.log"
LOG_ERR="${LOG_DIR}/daily_engine.stderr.log"

mkdir -p "$LOG_DIR"

install() {
    if [ -f "$PLIST_PATH" ]; then
        echo "Already installed. Uninstall first: bash $0 uninstall"
        exit 1
    fi

    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG_OUT}</string>

    <key>StandardErrorPath</key>
    <string>${LOG_ERR}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
EOF

    launchctl load "$PLIST_PATH"
    echo "Installed: $PLIST_PATH"
    echo "Schedule: daily at 06:00"
    echo "Logs: $LOG_DIR"
    echo ""
    echo "To test now: bash $0 run"
}

uninstall() {
    if [ ! -f "$PLIST_PATH" ]; then
        echo "Not installed."
        exit 0
    fi

    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo "Uninstalled: $PLIST_PATH"
}

status() {
    if [ -f "$PLIST_PATH" ]; then
        echo "Plist: $PLIST_PATH (exists)"
        launchctl list | grep "$LABEL" || echo "Not loaded in launchctl"
    else
        echo "Not installed"
    fi

    echo ""
    echo "Recent logs:"
    if [ -f "$LOG_OUT" ]; then
        echo "--- stdout (last 20 lines) ---"
        tail -20 "$LOG_OUT"
    fi
    if [ -f "$LOG_ERR" ]; then
        echo "--- stderr (last 10 lines) ---"
        tail -10 "$LOG_ERR"
    fi

    echo ""
    echo "Recent daily reports:"
    ls -lt "${PROJECT_DIR}/data/daily/"*.json 2>/dev/null | head -5 || echo "  (none)"
}

run_now() {
    echo "Running daily_engine.py now..."
    "$PYTHON" "$SCRIPT" 2>&1 | tee -a "$LOG_OUT"
}

case "${1:-help}" in
    install)   install ;;
    uninstall) uninstall ;;
    status)    status ;;
    run)       run_now ;;
    *)
        echo "Usage: bash $0 {install|uninstall|status|run}"
        echo ""
        echo "  install   - Set up launchd to run daily at 06:00"
        echo "  uninstall - Remove launchd job"
        echo "  status    - Show current status and recent logs"
        echo "  run       - Run immediately (manual trigger)"
        ;;
esac
