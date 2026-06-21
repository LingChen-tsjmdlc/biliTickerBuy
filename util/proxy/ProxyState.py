from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Callable


# 代理状态记录（dataclass）
@dataclass
class ProxyStateEntry:
    raw_proxy: str
    display_name: str
    cooldown_until: float = 0.0
    total_failures: int = 0
    total_successes: int = 0
    last_reason: str = ""
    recent_failures: deque[float] = field(default_factory=deque)

    def is_available(self, now: float | None = None) -> bool:
        """当前代理是否可用（未处于冷却期）"""
        current_time = time.time() if now is None else now
        return current_time >= self.cooldown_until

    def cooldown_remaining(self, now: float | None = None) -> int:
        """剩余冷却秒数"""
        current_time = time.time() if now is None else now
        return max(0, int(self.cooldown_until - current_time))


# 代理状态注册表，管理代理池的可用性、冷却与切换
class ProxyStateRegistry:
    def __init__(
        self,
        proxy_list: list[str],
        *,
        mask_proxy: Callable[[str], str],
        failure_threshold: int = 2,
        failure_window_seconds: float = 45.0,
        cooldown_seconds: float = 180.0,
    ):
        """初始化状态注册表"""
        self.failure_threshold = max(1, int(failure_threshold))
        self.failure_window_seconds = max(1.0, float(failure_window_seconds))
        self.cooldown_seconds = max(1.0, float(cooldown_seconds))
        self.current_index = 0
        self.states = [
            ProxyStateEntry(
                raw_proxy=proxy,
                display_name=mask_proxy(proxy) or proxy,
            )
            for proxy in proxy_list
        ]

    def set_current_index(self, index: int) -> None:
        """设置当前代理索引"""
        if index < 0 or index >= len(self.states):
            raise IndexError("proxy index out of range")
        self.current_index = index

    def current_state(self) -> ProxyStateEntry:
        """获取当前代理状态条目"""
        return self.states[self.current_index]

    def current_display_name(self) -> str:
        """当前代理显示名称"""
        return self.current_state().display_name

    def _trim_failures(self, state: ProxyStateEntry, now: float) -> None:
        """清理超出时间窗口的失败记录"""
        window_start = now - self.failure_window_seconds
        while state.recent_failures and state.recent_failures[0] < window_start:
            state.recent_failures.popleft()

    def record_current_success(self) -> None:
        """记录当前代理成功，清空失败记录"""
        state = self.current_state()
        state.total_successes += 1
        state.recent_failures.clear()

    def record_current_failure(self, reason: str) -> bool:
        """记录当前代理失败，达阈值时触发冷却"""
        now = time.time()
        state = self.current_state()
        state.total_failures += 1
        state.last_reason = reason
        state.recent_failures.append(now)
        self._trim_failures(state, now)
        if len(state.recent_failures) < self.failure_threshold:
            return False
        state.cooldown_until = max(state.cooldown_until, now + self.cooldown_seconds)
        state.recent_failures.clear()
        return True

    def available_count(self, now: float | None = None) -> int:
        """当前可用代理数量"""
        current_time = time.time() if now is None else now
        return sum(1 for state in self.states if state.is_available(current_time))

    def cooldown_count(self, now: float | None = None) -> int:
        """当前冷却中的代理数量"""
        current_time = time.time() if now is None else now
        return sum(1 for state in self.states if not state.is_available(current_time))

    def has_available_proxy(self, now: float | None = None) -> bool:
        """是否存在可用代理"""
        return self.available_count(now) > 0

    def is_current_available(self, now: float | None = None) -> bool:
        """当前代理是否可用"""
        return self.current_state().is_available(now)

    def switch_to_next_available(self) -> bool:
        """切换到下一个可用代理"""
        now = time.time()
        if len(self.states) <= 1:
            return False
        for offset in range(1, len(self.states)):
            next_index = (self.current_index + offset) % len(self.states)
            if self.states[next_index].is_available(now):
                self.current_index = next_index
                return True
        return False

    def ensure_current_available(self) -> bool:
        """确保当前代理可用，不可用时自动切换"""
        if self.is_current_available():
            return True
        return self.switch_to_next_available()

    def current_status_text(self) -> str:
        """当前代理状态摘要文本"""
        return (
            f"{self.current_display_name()} | "
            f"可用 {self.available_count()}/{len(self.states)} | "
            f"冷却 {self.cooldown_count()}"
        )

    def describe_all_states(self) -> str:
        """描述所有代理的可用/冷却状态"""
        now = time.time()
        parts: list[str] = []
        for index, state in enumerate(self.states):
            label = state.display_name
            if index == self.current_index:
                label += "(当前)"
            if state.is_available(now):
                status = "可用"
            else:
                status = f"冷却 {state.cooldown_remaining(now)} 秒"
            parts.append(f"{label}:{status}")
        return "；".join(parts)
