"""
全局常量定义

所有可配置默认值集中在此，避免散落各处。运行时可通过 CLI 参数覆盖。
"""

import datetime

# ── 时区 ──
# 北京时间（UTC+8），用于开票倒计时、日志时间戳等与 B 站服务端对齐的场景
BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8), name="Asia/Shanghai")

# ── 基础 URL ──
BASE_URL = "https://show.bilibili.com"
MEOW_API_BASE = "https://api.chuckfang.com"

# ── 应用标识 ──
PACKAGE_NAME = "bilitickerbuy"
UPDATE_CHANNEL_KEY = "update_channel"
# Go 后端侧上传配置文件的状态 key
GO_UPLOADED_FILES_STATE_KEY = "go.uploaded_config_files"

# ── 日志路由 ──
_LOG_VIEW_ROUTE = "/__btb/logs/view"
_LOG_STREAM_ROUTE = "/__btb/logs/stream"

# ── 请求节奏 ──
# 创建订单的默认请求间隔（毫秒），控制发送频率，避免被风控
DEFAULT_REQUEST_INTERVAL = 1000
DEFAULT_RATE_LIMIT_DELAY_MS = 100
# 创建订单最大重试次数，超过此值本轮放弃，回到外层重新准备
DEFAULT_CREATE_RETRY_LIMIT = 20
# 每次 /createV2 返回 has_more_page 时，同一 batch 内连续发送的请求数
DEFAULT_CREATE_REQUEST_BATCH_SIZE = 3
# 开票前多少秒开始预热 HTTP/2 连接并刷新项目状态
WARMUP_AT_SECONDS = 5.0
# 倒计时阶段每隔多少秒播报一次剩余时间
COUNTDOWN_REPORT_INTERVAL_SECONDS = 15
# 外层 while isRunning 每次循环的额外间隔（ms），默认 0 不等待
DEFAULT_OUTER_LOOP_INTERVAL = 0

# ── 代理相关 ──
# 同一代理连续失败多少次后标记为不可用
DEFAULT_PROXY_MAX_CONSECUTIVE_FAILURES = 2
# 代理被标记不可用后的冷却时间（秒），冷却结束后重新尝试
DEFAULT_PROXY_COOLDOWN_SECONDS = 180
# 所有代理都不可用时的退避等待上限（秒），指数增长到此封顶
DEFAULT_PROXY_BACKOFF_MAX_SECONDS = 600

# ── HTTP 请求超时 ──
# 通用超时: (connect_timeout, read_timeout)，单位秒
DEFAULT_TIMEOUT = (3.05, 8)
# HTTP/2 连接超时细节: connect/read/write/pool
H2_TIMEOUT = {
    "connect": 3.05,
    "read": 5.0,
    "write": 5.0,
    "pool": 5.0,
}

# ── HTTP/2 连接池 ──
H2_LIMITS = {
    "max_keepalive_connections": 10,
    "max_connections": 20,
    "keepalive_expiry": 60.0,
}

# ── 日志与文件管理 ──
# 日志保留天数，超期自动清理
DEFAULT_LOG_RETENTION_DAYS = 7
# 单实例日志文件数量上限
DEFAULT_MAX_LOG_FILES = 200
# 运行目录（run_dirs）数量上限
DEFAULT_MAX_RUN_DIRS = 100
