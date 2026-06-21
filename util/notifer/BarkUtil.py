import json
import requests

from urllib.parse import urlparse
from util.notifer.Notifier import NotifierBase


# Bark通知器，通过Bark服务推送通知
class BarkNotifier(NotifierBase):
    def __init__(self, token, title, content, interval_seconds=10, duration_minutes=10):
        """初始化Bark通知器"""
        super().__init__(title, content, interval_seconds, duration_minutes)
        self.token = token

    def send_message(self, title, message):
        """通过Bark API发送通知"""
        headers = {"Content-Type": "application/json"}
        data = {
            "icon": "https://raw.githubusercontent.com/mikumifa/biliTickerBuy/refs/heads/main/assets/icon.ico",  # 推送LOGO
            "group": "biliTickerBuy",
            "url": "https://mall.bilibili.com/neul/index.html?page=box_me&noTitleBar=1",  # 跳转会员购链接
            "sound": "telegraph",  # 警告铃声
            "level": "critical",  # 重要警告
            "volume": "10",
        }
        if isinstance(self.token, str) and urlparse(self.token).scheme in {
            "http",
            "https",
        }:
            url = f"{self.token.rstrip('/')}/{title}/{message}"
        else:
            url = f"https://api.day.app/{self.token}/{title}/{message}"

        requests.post(url, headers=headers, data=json.dumps(data))
