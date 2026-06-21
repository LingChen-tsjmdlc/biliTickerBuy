import json
import requests

from util.notifer.Notifier import NotifierBase


# PushPlus 通知推送实现
class PushPlusNotifier(NotifierBase):
    def __init__(self, token, title, content, interval_seconds=10, duration_minutes=10):
        """初始化 PushPlus 通知器"""
        super().__init__(title, content, interval_seconds, duration_minutes)
        self.token = token

    def send_message(self, title, message):
        """发送推送消息到 PushPlus"""
        url = "http://www.pushplus.plus/send"
        headers = {"Content-Type": "application/json"}

        data = {"token": self.token, "content": message, "title": title}
        requests.post(url, headers=headers, data=json.dumps(data))
