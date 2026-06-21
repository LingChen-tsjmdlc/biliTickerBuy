import requests

from util.proxy.ProxyState import ProxyStateRegistry


# 代理管理器，管理代理列表、切换与状态追踪
class ProxyManager:
    def __init__(
        self,
        proxy_string: str = "none",
        *,
        failure_threshold: int = 2,
        cooldown_seconds: float = 180.0,
    ):
        """初始化代理管理器"""
        self.proxy_list = self.parse_proxy_list(proxy_string)
        if not self.proxy_list:
            raise ValueError("at least have none proxy")
        self.state_registry = ProxyStateRegistry(
            self.proxy_list,
            mask_proxy=self.mask_proxy_value,
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
        )

    @property
    def now_proxy_idx(self) -> int:
        return self.state_registry.current_index

    @now_proxy_idx.setter
    def now_proxy_idx(self, index: int) -> None:
        self.state_registry.set_current_index(index)

    @staticmethod
    def normalize_proxy_value(proxy: str) -> str:
        """标准化代理字符串（none/direct 统一为 none）"""
        proxy = (proxy or "").strip()
        if not proxy:
            return ""
        if proxy.lower() in {"none", "direct"}:
            return "none"
        return proxy

    @classmethod
    def parse_proxy_list(
        cls, proxy_string: str | None, include_direct_fallback: bool = False
    ) -> list[str]:
        """解析代理字符串为去重列表"""
        proxy_list = []
        if proxy_string:
            proxy_list = [
                cls.normalize_proxy_value(item)
                for item in proxy_string.split(",")
                if item and item.strip()
            ]

        normalized: list[str] = []
        seen: set[str] = set()
        for item in proxy_list:
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(item)

        if include_direct_fallback and "none" not in seen:
            normalized.insert(0, "none")

        return normalized

    @staticmethod
    def mask_proxy_value(proxy: str) -> str:
        """脱敏代理中的用户名密码"""
        proxy = (proxy or "").strip()
        if not proxy:
            return ""
        if proxy.lower() in {"none", "direct"}:
            return "直连"
        if "://" not in proxy:
            return proxy

        scheme, remainder = proxy.split("://", 1)
        if "@" not in remainder:
            return proxy

        _, host_part = remainder.rsplit("@", 1)
        return f"{scheme}://***:***@{host_part}"

    @classmethod
    def mask_proxy_string(cls, proxy_string: str | None) -> str:
        """脱敏整个代理字符串"""
        proxies = cls.parse_proxy_list(proxy_string)
        masked = [cls.mask_proxy_value(proxy) for proxy in proxies]
        return ",".join(item for item in masked if item)

    @property
    def current_proxy(self) -> str:
        """当前代理原始字符串"""
        return self.proxy_list[self.now_proxy_idx]

    @property
    def current_proxy_display(self) -> str:
        """当前代理显示名称（脱敏后）"""
        return self.mask_proxy_value(self.current_proxy)

    def current_proxy_status(self) -> str:
        """当前代理状态文本"""
        return self.state_registry.current_status_text()

    def proxy_pool_status(self) -> str:
        """代理池全部状态描述"""
        return self.state_registry.describe_all_states()

    def snapshot(self) -> int:
        """保存当前代理索引快照"""
        return self.now_proxy_idx

    def restore(self, index: int) -> None:
        """恢复代理索引"""
        self.now_proxy_idx = index

    def apply_to_session(self, session: requests.Session) -> None:
        """将当前代理应用到 requests 会话"""
        session.trust_env = False
        if self.current_proxy == "none":
            session.proxies = {}
            return
        session.proxies = {
            "http": self.current_proxy,
            "https": self.current_proxy,
        }

    def rotate(self) -> bool:
        """轮转到下一个可用代理"""
        return self.state_registry.switch_to_next_available()

    def ensure_current_available(self) -> bool:
        """确保当前代理可用（必要时切换）"""
        return self.state_registry.ensure_current_available()

    def has_available_proxy(self) -> bool:
        """代理池中是否有可用代理"""
        return self.state_registry.has_available_proxy()

    def is_current_proxy_available(self) -> bool:
        """当前代理是否可用"""
        return self.state_registry.is_current_available()

    def mark_current_success(self) -> None:
        """标记当前代理成功"""
        self.state_registry.record_current_success()

    def mark_current_failure(self, reason: str) -> bool:
        """标记当前代理失败，返回是否触发冷却"""
        return self.state_registry.record_current_failure(reason)
