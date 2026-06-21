import json
import requests

from util.notifer.Notifier import NotifierBase


# Server酱Turbo通知器，通过Server酱Turbo API推送通知
class ServerChanTurboNotifier(NotifierBase):
    def __init__(self, token, title, content, interval_seconds=10, duration_minutes=10):
        """初始化Server酱Turbo通知器"""
        super().__init__(title, content, interval_seconds, duration_minutes)
        self.token = token

    def send_message(self, title, message):
        """通过Server酱Turbo API发送通知"""
        url = f"https://sctapi.ftqq.com/{self.token}.send"
        headers = {"Content-Type": "application/json"}

        data = {"desp": message, "title": title}
        requests.post(url, headers=headers, data=json.dumps(data))


# Server酱3通知器，通过Server酱3 API推送通知
class ServerChan3Notifier(NotifierBase):
    def __init__(
        self, api_url, title, content, interval_seconds=10, duration_minutes=10
    ):
        """初始化Server酱3通知器"""
        super().__init__(title, content, interval_seconds, duration_minutes)
        self.api_url = api_url

    def send_message(self, title, message):
        """通过Server酱3 API发送通知"""
        headers = {"Content-Type": "application/json"}
        data = {"title": title, "desp": message}
        requests.post(self.api_url, headers=headers, data=json.dumps(data))
