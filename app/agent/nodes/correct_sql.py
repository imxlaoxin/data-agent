import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.llm.llm import llm
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.prompt_loader.load_prompt import load_prompt

"""
有界反思循环 (Bounded Reflection Loop):
    大模型写错 SQL -> validate_sql 发现错误 -> correct_sql 尝试修正 -> 打回 validate_sql 再次检查 -> 如果还错，再回 correct_sql（最多循环 3 次）。
若 3 次后大模型依然无法写出合法的 SQL，Agent 会优雅地停止执行，避免对数据库造成负担，同时前端也能收到明确的报错提示。
"""
async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '校正SQL'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    # 获取当前重试次数，默认为 0
    current_retry = state.get('retry_count', 0)

    try:
        prompt = PromptTemplate(template=load_prompt('correct_sql'), input_variables=[
            'table_infos', 'metric_infos', 'date_info', 'db_info', 'query', 'sql', 'error'
        ])
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        sql: str = await chain.ainvoke({
            'table_infos': yaml.dump(state['table_infos'], allow_unicode=True, sort_keys=False),
            'metric_infos': yaml.dump(state['metric_infos'], allow_unicode=True, sort_keys=False),
            'date_info': yaml.dump(state['date_info'], allow_unicode=True, sort_keys=False),
            'db_info': yaml.dump(state['db_info'], allow_unicode=True, sort_keys=False),
            'query': state['query'],
            'sql': state['sql'],
            'error': state['error']
        })

        logger.info(f'correct_sql success (attempt {current_retry + 1}): {sql}')
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        # 将累加后的 retry_count 一并返回
        return {'sql': sql, 'retry_count': current_retry + 1}
    except Exception as e:
        logger.error(f'correct_sql fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise