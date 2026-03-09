// PM2 ecosystem — 7x24 全球信息差系统
module.exports = {
  apps: [
    {
      name: "arbitrage-api",
      script: "src/api_server.py",
      interpreter: "python3",
      cwd: __dirname,
      env: { ARBITRAGE_PORT: "8899" },
      autorestart: true,
      max_restarts: 50,
      restart_delay: 5000,
      log_file: "data/logs/api.log",
      error_file: "data/logs/api-error.log",
      out_file: "data/logs/api-out.log",
      time: true,
    },
    {
      name: "arbitrage-scanner",
      script: "src/daily_engine.py",
      interpreter: "python3",
      cwd: __dirname,
      cron_restart: "0 6,12,18,0 * * *",  // 每6小时扫描一次
      autorestart: false,  // cron触发，不自动重启
      log_file: "data/logs/scanner.log",
      error_file: "data/logs/scanner-error.log",
      out_file: "data/logs/scanner-out.log",
      time: true,
    },
  ],
};
