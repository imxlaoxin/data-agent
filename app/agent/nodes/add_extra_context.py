from datetime import date

from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState, DBInfoState
from langgraph.runtime import Runtime


async def add_extra_context(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '增加额外上下文'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        context = runtime.context
        dw_mysql_repository = context['dw_mysql_repository']

        today = date.today()
        date_str = today.strftime("%Y-%m-%d")
        weekday = today.strftime("%A")
        quarter = f'Q{(today.month - 1) // 3 + 1}'
        date_info: DateInfoState = DateInfoState(date=date_str, weekday=weekday, quarter=quarter)

        db_info: DBInfoState = await dw_mysql_repository.get_db_info()

        logger.info(f'add_extra_context success: date_info: {date_info}, db_info: {db_info}')
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        return {'date_info': date_info, 'db_info': db_info}
    except Exception as e:
        logger.error(f'add_extra_context fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise


if __name__ == '__main__':
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")
    weekday = today.strftime("%A")
    quarter = f'Q{(today.month - 1) // 3 + 1}'
    print(date_str, weekday, quarter)