from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime


async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '执行SQL'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        sql = state['sql']
        dw_mysql_repository = runtime.context['dw_mysql_repository']

        ret: list[dict] = await dw_mysql_repository.execute_sql(sql)

        writer({'type': 'progress', 'step': step, 'status': 'success'})
        writer({'type': 'result', 'data': ret})
        logger.info(f'execute_sql success: {ret}')
        return state
    except Exception as e:
        logger.error(f'execute_sql fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        # 尝试三次纠正SQL，若还是错误则返回完整的错误信息
        return {'error': f"数据库执行运行时异常: {str(e)}"}
