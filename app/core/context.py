from contextvars import ContextVar

# ContextVar: 协程级变量
# 加default默认值，保证在不是通过请求的过程不影响日志框架的使用(构建元数据库)
req_ctx_id_var: ContextVar[str] = ContextVar('request_id', default='1')
