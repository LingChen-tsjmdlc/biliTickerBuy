# B站网络连接异常
class BiliConnectionError(RuntimeError):
    """初始化连接异常"""
    def __init__(self, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause
