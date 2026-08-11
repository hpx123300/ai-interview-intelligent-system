"""LLM 调用容错：指数退避重试，提升 API 偶发失败下的稳定性。"""

import time
from functools import wraps


def with_retry(attempts: int = 3, base_delay: float = 1.0, backoff: float = 2.0):
    """装饰器：重试被装饰函数，指数退避；重试耗尽后抛出最后一次异常。"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for i in range(attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - 重试需捕获所有 API 异常
                    last_exc = exc
                    if i < attempts - 1:
                        time.sleep(min(base_delay * (backoff**i), 8.0))
            raise last_exc

        return wrapper

    return decorator
