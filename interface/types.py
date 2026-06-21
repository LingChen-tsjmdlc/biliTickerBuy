# 公共数据类型定义
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# 配置验证结果，包含成功标志、错误和警告列表
@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_config: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """将验证结果转为字典。"""
        return asdict(self)


# 抢票任务记录，跟踪任务状态、日志和支付信息
@dataclass
class BuyTaskRecord:
    task_id: str
    status: str
    detail: str
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    payment_qr_url: str | None = None
    logs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """将任务记录转为字典。"""
        return asdict(self)