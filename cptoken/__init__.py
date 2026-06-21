"""
cptoken — B 站 ctoken 生成与浏览器指纹模拟

这是整个抢票工具最核心的模块。B 站会员购的 /prepare、/createV2 等接口
要求在请求体中携带 ctoken，服务端用其验证请求是否来自「真实浏览器」。

ctoken 本质是一个基于浏览器环境指纹 + 时间戳 + 随机值编码的 base64 字符串。
本模块负责：
1. 模拟随机的浏览器窗口状态（分辨率、滚动位置等）
2. 从窗口状态派生出 m1~m9 等参数（模拟 JS 侧 collect_token 逻辑）
3. 随时间推移更新 timer/timediff（模拟浏览器 tab 打开时长）
4. 编码为 base64 字符串供请求使用
"""

import base64
from dataclasses import asdict, dataclass, field
import logging
import random
import time
from typing import TypedDict

try:
    from loguru import logger
except ImportError:  # pragma: no cover - test/runtime fallback
    logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 核心编码函数
# ──────────────────────────────────────────────

def generate_ctoken(
    m1: int = -1,
    touchend: int = -1,
    m2: int = -1,
    visibilitychange: int = -1,
    m3: int = -1,
    m4: int = -1,
    openWindow: int = -1,
    m5: int = -1,
    timer: int = -1,
    timediff: float = 0,
    m6: int = -1,
    m7: int = -1,
    m8: int = -1,
    m9: int = -1,
    beforeunload: int = -1,
    ticket_collection_t: int = 0,
) -> str:
    """
    将浏览器指纹参数编码为 base64 ctoken 字符串。

    编码格式:
        每个参数 hex(1字节) + \x00 分隔
        timer 和 timediff 占 2 字节（各拆分高低位）
        最终 base64 编码

    参数: 与 B 站前端 collect_token 函数一一对应，-1 表示未提供，由本函数填充随机值。
    """
    _ = ticket_collection_t  # 保留参数兼容性，当前未直接参与编码

    # ── 未提供参数 → 随机填充 ──
    if touchend == -1:
        touchend = random.randint(30, 50)
    if visibilitychange == -1:
        visibilitychange = random.randint(10, 50)
    if beforeunload == -1:
        beforeunload = openWindow if openWindow != -1 else random.randint(10, 50)
    if timer == -1:
        timer = random.randint(1, 10)

    def _b1(x: int) -> bytes:
        """int → 单字节，溢出取 0xff"""
        try:
            return int(x).to_bytes(1, "big")
        except OverflowError:
            return b"\xff"

    # ── 按固定顺序编码 m1~m5 ──
    tb = (
        _b1(m1)
        + b"\x00"
        + _b1(touchend)
        + b"\x00"
        + _b1(m2)
        + b"\x00"
        + _b1(visibilitychange)
        + b"\x00"
        + _b1(m3)
        + b"\x00"
        + _b1(m4)
        + b"\x00"
        + _b1(beforeunload)
        + b"\x00"
        + _b1(m5)
        + b"\x00"
    )
    # ── timer: 2 字节高低位 ──
    try:
        tt = int(timer).to_bytes(2, "big")
        tb += _b1(tt[0]) + b"\x00" + _b1(tt[1]) + b"\x00"
    except OverflowError:
        tb += b"\xff\x00\xff\x00"
    # ── timediff: 2 字节高低位（秒级） ──
    try:
        tc = int(float(timediff)).to_bytes(2, "big")
        tb += _b1(tc[0]) + b"\x00" + _b1(tc[1]) + b"\x00"
    except OverflowError:
        tb += b"\xff\x00\xff\x00"
    # ── m6~m9 ──
    tb += _b1(m6) + b"\x00" + _b1(m7) + b"\x00" + _b1(m8) + b"\x00" + _b1(m9) + b"\x00"
    return base64.b64encode(tb).decode("utf-8")


# ──────────────────────────────────────────────
# 快照：某一时刻的 ctoken 参数集合
# ──────────────────────────────────────────────

@dataclass(slots=True)
class CTokenSnapshot:
    """
    某一时刻 ctoken 参数的不变快照。

    与 CTokenRuntimeState 的区别:
        - RuntimeState 随时间动态变化（timer 递增、timediff 累积）
        - Snapshot 是 RuntimeState 在特定时刻的冻结副本，可直接生成 ctoken
    """
    m1: int
    touchend: int
    m2: int
    visibilitychange: int
    m3: int
    m4: int
    openWindow: int
    m5: int
    timer: int
    timediff: float
    m6: int
    m7: int
    m8: int
    m9: int
    beforeunload: int = -1
    ticket_collection_t: int = 0
    base_timer: int = 0

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)

    def kwargs(self) -> dict[str, int | float]:
        """转为 generate_ctoken 可直接 ** 展开的参数字典"""
        return {
            "m1": self.m1,
            "touchend": self.touchend,
            "m2": self.m2,
            "visibilitychange": self.visibilitychange,
            "m3": self.m3,
            "m4": self.m4,
            "openWindow": self.openWindow,
            "m5": self.m5,
            "timer": self.timer,
            "timediff": self.timediff,
            "m6": self.m6,
            "m7": self.m7,
            "m8": self.m8,
            "m9": self.m9,
            "beforeunload": self.beforeunload,
        }

    def generate_ctoken(self) -> str:
        """生成 ctoken（别名）"""
        return self.generate_prepare_ctoken()

    def generate_prepare_ctoken(self) -> str:
        """生成 /prepare 接口用的 ctoken（含 openWindow, beforeunload）"""
        return generate_ctoken(**self.kwargs())

    def generate_create_ctoken(self) -> str:
        """生成 /createV2 接口用的 ctoken（不含 openWindow, beforeunload）"""
        fields = self.kwargs()
        fields.pop("openWindow", None)
        fields.pop("beforeunload", None)
        return generate_ctoken(**fields)


# ──────────────────────────────────────────────
# 浏览器窗口状态模拟
# ──────────────────────────────────────────────

class BrowserWindowState(TypedDict):
    """模拟浏览器的窗口与屏幕信息，用于派生 ctoken 的 m1~m9 等参数"""
    scrollX: int
    scrollY: int
    innerWidth: int
    innerHeight: int
    outerWidth: int
    outerHeight: int
    screenX: int
    screenY: int
    screenWidth: int
    screenHeight: int
    screenAvailWidth: int
    screenAvailHeight: int


def generate_browser_window_state(
    *,
    screen_width: int | None = None,
    screen_height: int | None = None,
    maximized: bool | None = None,
    scroll: bool = False,
) -> BrowserWindowState:
    """
    随机生成一组合理的浏览器窗口状态。

    模拟逻辑:
      - 从常见分辨率中随机选取屏幕尺寸（1920x1080, 2560x1440...）
      - 65% 概率模拟最大化窗口（否则 60%~90% 屏幕占比）
      - Chrome 窗口边框/标签栏占用随机偏移
      - inner 尺寸 = outer - Chrome 镶边
    """
    common_screens = [
        (1920, 1080),
        (2560, 1440),
        (1366, 768),
        (1440, 900),
        (1536, 864),
        (1600, 900),
        (1280, 720),
    ]

    if screen_width is None or screen_height is None:
        screen_width, screen_height = random.choice(common_screens)

    taskbar_height = random.choice([40, 48, 56, 64])
    screen_avail_width = screen_width
    screen_avail_height = screen_height - taskbar_height

    if maximized is None:
        maximized = random.random() < 0.65

    # Chrome 窗口镶边偏移量
    chrome_width_delta = random.choice([0, 8, 12, 16])
    chrome_height_delta = random.choice([80, 88, 96, 104, 112, 120])

    if maximized:
        outer_width = screen_avail_width
        outer_height = screen_avail_height
        screen_x = 0
        screen_y = 0
        inner_width = outer_width - chrome_width_delta
        inner_height = outer_height - chrome_height_delta
    else:
        outer_width = random.randint(
            int(screen_avail_width * 0.60),
            int(screen_avail_width * 0.90),
        )
        outer_height = random.randint(
            int(screen_avail_height * 0.60),
            int(screen_avail_height * 0.90),
        )
        max_x = max(0, screen_avail_width - outer_width)
        max_y = max(0, screen_avail_height - outer_height)
        screen_x = random.randint(0, max_x)
        screen_y = random.randint(0, max_y)
        inner_width = outer_width - chrome_width_delta
        inner_height = outer_height - chrome_height_delta

    inner_width = max(320, inner_width)
    inner_height = max(240, inner_height)

    if scroll:
        scroll_x = random.choice([0, 0, 0, random.randint(1, 200)])
        scroll_y = random.choice([0, random.randint(50, 2000)])
    else:
        scroll_x = 0
        scroll_y = 0

    return {
        "scrollX": scroll_x,
        "scrollY": scroll_y,
        "innerWidth": inner_width,
        "innerHeight": inner_height,
        "outerWidth": outer_width,
        "outerHeight": outer_height,
        "screenX": screen_x,
        "screenY": screen_y,
        "screenWidth": screen_width,
        "screenHeight": screen_height,
        "screenAvailWidth": screen_avail_width,
        "screenAvailHeight": screen_avail_height,
    }


# ──────────────────────────────────────────────
# 运行时状态：随时间变化的 ctoken 参数
# ──────────────────────────────────────────────

@dataclass(slots=True)
class CTokenRuntimeState:
    """
    ctoken 运行时状态，timer 和 timediff 随真实时间流逝自动增长。

    设计原因:
      B 站前端 JS 通过 performance.now() 计算页面打开时长。
      如果不模拟时间增长，服务端会检测到 ctoken 时间停滞 → 拒绝请求。

    生命周期:
      1. init_ctoken_state() 初始化 → 随机生成 m1~m9, base_timer, créated_at_ms
      2. 每次发请求前 snapshot() → 根据当前时间计算 timer/timediff
      3. snapshot 转 CTokenSnapshot → generate_ctoken() → 最终 token
    """
    m1: int
    touchend: int
    m2: int
    visibilitychange: int
    m3: int
    m4: int
    openWindow: int
    m5: int
    m6: int
    m7: int
    m8: int
    m9: int
    beforeunload: int = field(default_factory=lambda: random.randint(1, 3))
    ticket_collection_t: int = 0          # 开票时间（毫秒时间戳），用于 timediff 计算
    base_timer: int = field(default_factory=lambda: random.randint(10, 100))  # 初始计时器值
    base_timediff: float = 0              # 手动偏移量（NTP 同步用）
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))  # 状态创建时间

    def snapshot(self, now_ms: int | None = None) -> CTokenSnapshot:
        """
        取当前时刻的 CTokenSnapshot。

        timer  = base_timer + 已过秒数（模拟页面存活时长）
        timediff = base_timediff + 距开票时间的秒数
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        elapsed_seconds = max(0.0, (now_ms - self.created_at_ms) / 1000)
        timediff = self.base_timediff
        if self.ticket_collection_t > 0:
            timediff += max(0.0, (now_ms - self.ticket_collection_t) / 1000)
        return CTokenSnapshot(
            m1=self.m1,
            touchend=self.touchend,
            m2=self.m2,
            visibilitychange=self.visibilitychange,
            m3=self.m3,
            m4=self.m4,
            openWindow=self.openWindow,
            m5=self.m5,
            timer=self.base_timer + int(elapsed_seconds),
            timediff=timediff,
            m6=self.m6,
            m7=self.m7,
            m8=self.m8,
            m9=self.m9,
            beforeunload=self.beforeunload,
            ticket_collection_t=self.ticket_collection_t,
            base_timer=self.base_timer,
        )

    def kwargs(self, now_ms: int | None = None) -> dict[str, int | float]:
        return self.snapshot(now_ms=now_ms).kwargs()


# ──────────────────────────────────────────────
# 初始化函数
# ──────────────────────────────────────────────

def init_ctoken_state(
    browser_window_state: BrowserWindowState | None = None,
    history_length: int = random.randint(2, 10),
    user_agent_length: int = 140,
    href_length: int = 76,
    device_pixel_ratio: float = 4.0,
    ticket_collection_t: int = 0,
) -> CTokenRuntimeState:
    """
    创建新的 CTokenRuntimeState，从浏览器窗口状态派生出 m1~m9。

    派生算法 (derive_d):
      将窗口属性（scrollX/Y, innerWidth/Height 等）按 index 混入哈希，
      加上 current_time_ms % 256 作为 salt → 取低 8 位。
      这与 B 站前端 collect_token 的散列逻辑对应。
    """
    if browser_window_state is None:
        browser_window_state = generate_browser_window_state()

    def derive_d(index: int) -> int:
        """按 index 从窗口状态数组派生 0~255 之间的散列值"""
        now_mod_256 = int(time.time() * 1000) % 256
        values = [
            browser_window_state["scrollX"],
            browser_window_state["scrollY"],
            browser_window_state["innerWidth"],
            browser_window_state["innerHeight"],
            browser_window_state["outerWidth"],
            browser_window_state["outerHeight"],
            browser_window_state["screenX"],
            browser_window_state["screenY"],
            browser_window_state["screenWidth"],
            browser_window_state["screenHeight"],
            browser_window_state["screenAvailWidth"],
            history_length,
            user_agent_length,
            href_length,
            round(10 * (device_pixel_ratio or 1)),
            now_mod_256,
        ]
        return (values[index % 16] + values[(3 * index) % 16] + 17 * index) & 255

    state = CTokenRuntimeState(
        m1=derive_d(1),
        touchend=0,
        m2=derive_d(2),
        visibilitychange=0,
        m3=derive_d(3),
        m4=derive_d(4),
        openWindow=random.randint(1, 3),
        m5=derive_d(5),
        m6=derive_d(6),
        m7=derive_d(7),
        m8=derive_d(8),
        m9=derive_d(9),
        ticket_collection_t=ticket_collection_t,
        created_at_ms=ticket_collection_t or int(time.time() * 1000),
    )
    logger.info(state.snapshot().to_dict())
    return state


def sim_ctoken_state(
    before_state: CTokenRuntimeState,
    now_ms: int | None = None,
) -> CTokenSnapshot:
    """
    基于上一轮的状态模拟新的快照（token 过期后重建用）。

    相比直接 snapshot():
      - touchend, openWindow, visibilitychange 有概率 +1/+2（模拟用户继续操作）
      - timer/timediff 基于 ticket_collection_t 重新计算
    """
    if now_ms is None:
        now_ms = int(time.time() * 1000)

    source = before_state.snapshot(now_ms=before_state.created_at_ms)
    ticket_collection_t = source.ticket_collection_t
    base_timer = source.base_timer or source.timer
    touchend_add = random.choice([0, 0, 1, 2])
    open_window_add = random.choices([0, 0, 1], weights=[60, 20, 20], k=1)[0]
    visibilitychange_add = random.choices([0, 0, 1], weights=[60, 20, 20], k=1)[0]

    snapshot = CTokenSnapshot(
        m1=source.m1,
        touchend=source.touchend + touchend_add,
        m2=source.m2,
        visibilitychange=source.visibilitychange + visibilitychange_add,
        m3=source.m3,
        m4=source.m4,
        openWindow=source.openWindow + open_window_add,
        m5=source.m5,
        timer=base_timer + int((now_ms - ticket_collection_t) / 1000),
        timediff=max(0.0, (now_ms - ticket_collection_t) / 1000),
        m6=source.m6,
        m7=source.m7,
        m8=source.m8,
        m9=source.m9,
        ticket_collection_t=ticket_collection_t,
        base_timer=base_timer,
    )
    return snapshot


__all__ = [
    "CTokenRuntimeState",
    "CTokenSnapshot",
    "generate_ctoken",
    "generate_browser_window_state",
    "init_ctoken_state",
    "sim_ctoken_state",
]
