import secrets
import time
from collections.abc import Callable

import loguru
import requests
from requests import Response
from util.Constant import H2_LIMITS, H2_TIMEOUT
from util.request.BrowerState import (
    BrowserFingerprintState,
    build_headers_from_browser_state,
    finalize_device_id,
    generate_browser_fingerprint_state,
)
from util.request.CookieManager import CookieManager
from util.request.exceptions import BiliConnectionError, BiliRateLimitError
from util.proxy.ProxyManager import ProxyManager


# B站请求客户端，封装HTTP/2请求、代理管理与Cookie维护
class BiliRequest:
    """初始化请求客户端，构建浏览器指纹、代理与Cookie管理器"""
    def __init__(
        self,
        headers=None,
        cookies=None,
        cookies_config_path=None,
        proxy: str = "none",
        browser_state: BrowserFingerprintState | None = None,
        proxy_failure_threshold: int = 2,
        proxy_cooldown_seconds: float = 180.0,
    ):
        self.browser_state = browser_state or generate_browser_fingerprint_state()
        self.deviceId = finalize_device_id(secrets.token_hex(16))
        self.session = requests.Session()
        self.proxy_manager = ProxyManager(
            proxy,
            failure_threshold=proxy_failure_threshold,
            cooldown_seconds=proxy_cooldown_seconds,
        )
        self.cookieManager = CookieManager(cookies_config_path, cookies)
        self.headers = build_headers_from_browser_state(
            self.browser_state,
            base_headers=headers,
            referer="https://show.bilibili.com/",
            content_type="application/x-www-form-urlencoded",
        )
        self.request_count = 0  # 记录请求次数
        self.proxy_manager.apply_to_session(self.session)
        self._h2_client = None
        self.createTime = int(time.time() * 1000)
        self._handle_100001: Callable[[], None] | None = None

    def _rotate_proxy(self, reason: str) -> bool:
        """切换到下一个代理"""
        if not self.proxy_manager.rotate():
            return False
        self.proxy_manager.apply_to_session(self.session)
        self._invalidate_h2_client()
        return True

    def _invalidate_h2_client(self):
        """关闭并清除当前HTTP/2客户端连接"""
        if self._h2_client is None:
            return
        try:
            self._h2_client.close()
        except Exception:
            pass
        self._h2_client = None

    def get_user_agent(self) -> str:
        """获取当前User-Agent"""
        return self.headers.get("user-agent", "")

    def snapshot_proxy_state(self) -> int:
        """保存当前代理状态快照"""
        return self.proxy_manager.snapshot()

    def restore_proxy_state(self, state: int) -> None:
        """恢复之前保存的代理状态"""
        self.proxy_manager.restore(state)
        self.proxy_manager.apply_to_session(self.session)
        self._invalidate_h2_client()

    def clear_request_count(self):
        """清零请求计数"""
        self.request_count = 0

    def set_100001_handler(self, handler: Callable[[], None] | None) -> None:
        """设置错误码100001的处理回调"""
        self._handle_100001 = handler

    def handle_100001(self, err: int) -> bool:
        """触发100001错误码的维护处理逻辑"""
        if err != 100001 or self._handle_100001 is None:
            return False
        loguru.logger.warning("错误码 100001，执行维护逻辑")
        self._handle_100001()
        return True

    def get(self, url, data=None, isJson=False):
        """发送GET请求"""
        return self._request("get", url, data=data, isJson=isJson)

    def switch_proxy(self):
        """手动切换代理"""
        return self._rotate_proxy("手动切换代理")

    def post(self, url, data=None, isJson=False):
        """发送POST请求"""
        return self._request("post", url, data=data, isJson=isJson)

    def current_proxy_display(self) -> str:
        """当前代理的显示名称"""
        return self.proxy_manager.current_proxy_display

    def current_proxy_status(self) -> str:
        """当前代理状态描述"""
        return self.proxy_manager.current_proxy_status()

    def proxy_pool_status(self) -> str:
        """代理池整体状态信息"""
        return self.proxy_manager.proxy_pool_status()

    def replace_proxy_pool(self, proxy_string: str) -> None:
        self.proxy_manager.replace_proxy_list(proxy_string)
        self.proxy_manager.apply_to_session(self.session)
        self._invalidate_h2_client()

    def has_available_proxy(self) -> bool:
        """是否有可用代理"""
        return self.proxy_manager.has_available_proxy()

    def is_current_proxy_available(self) -> bool:
        """当前代理是否可用"""
        return self.proxy_manager.is_current_proxy_available()

    def ensure_active_proxy(self) -> bool:
        """确保当前代理可用，不可用则自动切换"""
        if not self.proxy_manager.ensure_current_available():
            return False
        self.proxy_manager.apply_to_session(self.session)
        return True

    def mark_current_proxy_failure(self, reason: str) -> bool:
        """标记当前代理失败，触发冷却"""
        return self.proxy_manager.mark_current_failure(reason)

    def mark_current_proxy_success(self) -> None:
        """标记当前代理请求成功"""
        self.proxy_manager.mark_current_success()

    def describe_non_json_response(
        self, response: Response, body_limit: int = 300
    ) -> str:
        """描述非JSON响应的基本信息（状态码、Content-Type、body预览）"""
        content_type = response.headers.get("Content-Type", "未知")
        body = response.text or ""
        body = body.replace("\r", "\\r").replace("\n", "\\n")
        if len(body) > body_limit:
            body = body[:body_limit] + "..."
        if not body:
            body = "<empty>"
        return (
            f"status={response.status_code}, "
            f"content_type={content_type}, "
            f"url={response.url}, "
            f"body_preview={body}"
        )

    def _build_h2_client(self):
        """构建带代理和超时配置的HTTP/2客户端"""
        import httpx

        proxies = self.session.proxies or {}
        proxy = proxies.get("https") or proxies.get("http") or None
        verify = (
            self.session.verify
            if isinstance(self.session.verify, (bool, str))
            else True
        )
        return httpx.Client(
            http2=True,
            verify=verify,
            proxy=proxy,
            timeout=httpx.Timeout(**H2_TIMEOUT),
            limits=httpx.Limits(**H2_LIMITS),
            headers={
                "accept": "*/*",
                "accept-encoding": "gzip, deflate, br, zstd",
                "connection": "keep-alive",
                "user-agent": self.headers.get("user-agent", ""),
            },
        )

    def prewarm_h2_connection(self, url: str) -> None:
        """预热HTTP/2连接，提前建立连接和设置Cookie"""
        import httpx

        if self._h2_client is None:
            self._h2_client = self._build_h2_client()
        client = self._h2_client
        client.headers["user-agent"] = self.headers.get("user-agent", "")
        for cookie in self.cookieManager.get_cookies(force=True) or []:
            name = cookie.get("name")
            value = cookie.get("value")
            if name and value is not None:
                client.cookies.set(name, value, domain=".bilibili.com")
        try:
            client.head(url)
        except httpx.HTTPError:
            pass

    def _h2_send(self, method: str, url, data=None, isJson=False):
        """通过HTTP/2客户端发送请求"""
        if self._h2_client is None:
            self._h2_client = self._build_h2_client()
        client = self._h2_client
        client.headers["user-agent"] = self.headers.get("user-agent", "")
        for cookie in self.cookieManager.get_cookies(force=True) or []:
            name = cookie.get("name")
            value = cookie.get("value")
            if name and value is not None:
                client.cookies.set(name, value, domain=".bilibili.com")
        if method.lower() == "post":
            return (
                client.post(url, json=data) if isJson else client.post(url, data=data)
            )
        return client.get(url, params=data)

    def _send_with_h2_recovery(self, method: str, url, data=None, isJson=False):
        """发送HTTP/2请求，异常时自动重建连接重试一次"""
        import httpx

        for attempt in range(2):
            try:
                return self._h2_send(method, url, data=data, isJson=isJson)
            except httpx.TimeoutException as exc:
                self._invalidate_h2_client()
                if attempt >= 1:
                    raise BiliConnectionError(
                        "网络请求超时：服务器响应过慢，请稍后重试",
                        cause=exc,
                    ) from exc
                loguru.logger.warning("HTTP 请求超时，已重建连接后重试: {}", exc)
            except httpx.LocalProtocolError as exc:
                self._invalidate_h2_client()
                if attempt >= 1:
                    raise BiliConnectionError(
                        "网络连接异常：HTTP/2 连接已断开，重试后仍失败，请稍后再试",
                        cause=exc,
                    ) from exc
                loguru.logger.warning("HTTP/2 连接状态异常，已重建连接后重试: {}", exc)

    def _request(self, method: str, url, data=None, isJson=False):
        """统一请求入口，处理412/429状态码和登录状态检查"""
        response = self._send_with_h2_recovery(
            method,
            url,
            data=data,
            isJson=isJson,
        )

        if response.status_code == 412:
            self.request_count += 1
            return response
        if response.status_code == 429:
            raise BiliRateLimitError(
                "请求被限流(HTTP 429)",
                response=response,
            )

        response.raise_for_status()
        self.clear_request_count()
        self.mark_current_proxy_success()
        if response.json().get("msg", "") == "请先登录":
            raise RuntimeError("当前未登录，请重新登陆")
        return response

    def get_request_name(self):
        """通过B站API获取当前登录用户名"""
        try:
            if not self.cookieManager.have_cookies():
                loguru.logger.warning("获取用户名失败，请重新登录")
                return "未登录"
            result = self.get("https://api.bilibili.com/x/web-interface/nav").json()
            return result["data"]["uname"]
        except Exception:
            return "未登录"
