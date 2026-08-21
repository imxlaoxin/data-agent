from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '校验SQL'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        sql = state['sql']
        context = runtime.context
        dw_mysql_repository = context['dw_mysql_repository']

        try:
            await dw_mysql_repository.validate_sql(sql)
            logger.info('validate_sql success: sql语法正确')
            writer({'type': 'progress', 'step': step, 'status': 'success'})
            return {'error': None}
        except Exception as err:
            logger.info(f'validate_sql: sql语法错误 error: {str(err)}')
            writer({'type': 'progress', 'step': step, 'status': 'success'})
            return {'error': str(err)}
    except Exception as e:
        logger.error(f'validate_sql fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise
