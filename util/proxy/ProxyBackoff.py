from __future__ import annotations


# 代理退避策略，指数增长延迟
class ProxyBackoff:
    def __init__(
        self,
        *,
        base_seconds: int = 30,
        factor: float = 2.0,
        max_seconds: int = 600,
    ):
        """初始化退避参数"""
        self.base_seconds = max(1, int(base_seconds))
        self.factor = max(1.0, float(factor))
        self.max_seconds = max(self.base_seconds, int(max_seconds))
        self.exhausted_rounds = 0
        self.notification_sent = False

    def next_delay_seconds(self) -> int:
        """计算下次延迟秒数"""
        delay = int(round(self.base_seconds * (self.factor**self.exhausted_rounds)))
        self.exhausted_rounds += 1
        return min(delay, self.max_seconds)

    def reset(self) -> None:
        """重置退避状态"""
        self.exhausted_rounds = 0
        self.notification_sent = False

    def should_notify(self) -> bool:
        """是否需要发送通知（仅首次触发）"""
        if self.notification_sent:
            return False
        self.notification_sent = True
        return True
