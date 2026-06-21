# B站请求限流异常
class BiliRateLimitError(RuntimeError):
    """初始化限流异常"""
    def __init__(self, message: str, *, response=None):
        super().__init__(message)
        self.response = response
