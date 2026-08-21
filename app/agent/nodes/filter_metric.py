import json
import os
import re
import time

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.llm.llm import llm
from app.agent.state import DataAgentState, MetricInfoState
from langgraph.runtime import Runtime

from app.prompt_loader.load_prompt import load_prompt


async def filter_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '过滤指标信息'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        query = state['query']
        metric_infos: list[MetricInfoState] = state['metric_infos']
        metric_infos_yaml = yaml.dump(metric_infos, allow_unicode=True, sort_keys=False)

        prompt = PromptTemplate(template=load_prompt('filter_metric_info'), input_variables=['query', 'metric_infos'])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        ret = await chain.ainvoke({'query': query, 'metric_infos': metric_infos_yaml})

        filtered_metric_infos: list[MetricInfoState] = [metric__info for metric__info in metric_infos if
                                                        metric__info['name'] in ret]

        # 用于调试，观察效果
        save_dir = get_safe_dir_name(query)
        os.makedirs(save_dir, exist_ok=True)
        with open(os.path.join(save_dir, 'filtered_metrics.json'), 'w', encoding='utf-8') as f:
            json.dump(filtered_metric_infos, f, ensure_ascii=False, indent=2)

        logger.info(
            f"filter_metric success: {[metric__info['name'] for metric__info in filtered_metric_infos]}")
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        return {'metric_infos': filtered_metric_infos}
    except Exception as e:
        logger.error(f'filter_metric fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise


def get_safe_dir_name(query: str) -> str:
    # 1. 替换非法路径字符（/ \ : * ? " < > |）为下划线
    clean_query = re.sub(r'[\\/:*?"<>|]', '_', query)
    # 2. 去除前后空格并截取前 30 个字符，防止路径过长
    clean_query = clean_query.strip()[:30]
    # 3. 拼接时间戳（精确到秒），避免覆盖
    # timestamp = time.strftime('%Y%m%d_%H%M%S')
    timestamp = time.strftime('%Y%m%d_%H%M')

    return f'temp_debug/{clean_query}_{timestamp}'
