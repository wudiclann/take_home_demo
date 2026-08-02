# Shared slowapi Limiter, keyed by client IP -- imported by main.py (to wire the
# exception handler/middleware) and by any route module that needs to decorate
# an endpoint with @limiter.limit(...).
#
# 共享的 slowapi 限流器（Limiter），按客户端 IP 区分——main.py 用它接入
# 异常处理器和中间件，各路由模块用它给接口加上 @limiter.limit(...) 装饰器。

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
