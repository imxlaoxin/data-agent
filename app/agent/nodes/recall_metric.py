from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.llm.llm import llm
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.entities.metric_info import MetricInfo
from app.prompt_loader.load_prompt import load_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '召回指标信息'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        context = runtime.context
        embedding_client = context['embedding_client']
        metric_qdrant_repository = context['metric_qdrant_repository']

        keywords = state['keywords']
        # 1. 使用LLM扩展关键词
        prompt = PromptTemplate(template=load_prompt('extend_keywords_for_metric_recall'), input_variables=['query'])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        ret = await chain.ainvoke(input={'query': state['query']})
        keywords.extend(ret)
        keywords = list(set(keywords))
        logger.info(f'【recall_metric】 llm extended keywords: {keywords}')
        # 2. 使用扩展后的关键词召回字段信息
        vectors = await embedding_client.aembed_documents(keywords)
        metric_id_map = {}
        for vector in vectors:
            metric_infos: list[MetricInfo] = await metric_qdrant_repository.metric_query(vector)
            for metric_info in metric_infos:
                if metric_info.id not in metric_id_map:
                    metric_id_map[metric_info.id] = metric_info
        retrieved_metrics: list[str] = list(metric_id_map.values())

        logger.info(f'recall_metric success: {metric_id_map.keys()}')
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        return {'retrieved_metrics': retrieved_metrics}
    except Exception as e:
        logger.error(f'recall_metric fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise

