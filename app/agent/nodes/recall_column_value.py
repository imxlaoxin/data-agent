import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.llm.llm import llm
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.entities.value_info import ValueInfo
from app.prompt_loader.load_prompt import load_prompt


async def recall_column_value(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '召回字段取值'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        context = runtime.context
        value_es_repository = context['value_es_repository']
        value_qdrant_repository = context['value_qdrant_repository']
        embedding_client = context['embedding_client']
        keywords = state['keywords']
        # 1. 使用LLM扩展关键词
        prompt = PromptTemplate(template=load_prompt('extend_keywords_for_value_recall'), input_variables=['query'])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        ret = await chain.ainvoke(input={'query': state['query']})
        keywords.extend(ret)
        keywords = list(set(keywords))
        logger.info(f'【recall_column_value】 llm extended keywords: {keywords}')
        # 2. 并发执行 ES 和 Qdrant 双路召回字段取值
        # value_id_map: dict[str, ValueInfo] = {}
        es_results: dict[str, ValueInfo] = {}
        qdrant_results: dict[str, ValueInfo] = {}

        # 2.1 ES 字面匹配
        async def es_search():
            for keyword in keywords:
                value_infos: list[ValueInfo] = await value_es_repository.value_query(keyword)
                for value_info in value_infos:
                    if value_info.id not in es_results:
                        es_results[value_info.id] = value_info

        # 2.2 Qdrant 语义匹配
        async def qdrant_search():
            vectors = await embedding_client.aembed_documents(keywords)
            for vector in vectors:
                value_infos: list[ValueInfo] = await value_qdrant_repository.value_query(vector)
                for value_info in value_infos:
                    if value_info.id not in qdrant_results:
                        qdrant_results[value_info.id] = value_info

        # 并发执行两路搜索
        await asyncio.gather(es_search(), qdrant_search())

        es_ids = set(es_results.keys())
        qdrant_ids = set(qdrant_results.keys())
        intersection_ids = es_ids & qdrant_ids  # 两者同时召回的
        only_es_ids = es_ids - qdrant_ids  # 仅 ES 召回的
        only_qdrant_ids = qdrant_ids - es_ids  # 仅 Qdrant 召回的

        logger.info(f"【召回效果对比】")
        logger.info(f"ES 独有召回数量: {len(only_es_ids)} | IDs: {only_es_ids}")
        logger.info(f"Qdrant 独有召回数量: {len(only_qdrant_ids)} | IDs: {only_qdrant_ids}")
        logger.info(f"两者重合召回数量: {len(intersection_ids)} | IDs: {intersection_ids}")

        # 合并两路结果供下游使用
        merged_map = {**es_results, **qdrant_results}
        retrieved_column_values: list[str] = list(merged_map.values())

        logger.info(f'recall_column_value success: {merged_map.keys()}')
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        return {'retrieved_column_values': retrieved_column_values}
    except Exception as e:
        logger.error(f'recall_column_value fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise
