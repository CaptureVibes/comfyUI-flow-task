from __future__ import annotations


class AppError(Exception):
    """所有应用业务异常的基类"""
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ValidationError(AppError):
    status_code = 400
    detail = "Validation error"


class InvalidStatusTransitionError(AppError):
    status_code = 400
    detail = "Invalid status transition"


class UpstreamError(AppError):
    """上游服务（ComfyUI、上传 API 等）调用失败"""
    status_code = 502
    detail = "Upstream service error"


class ComfyUIError(UpstreamError):
    detail = "ComfyUI service error"
