from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.llm.llm import llm
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.entities.column_info import ColumnInfo
from app.prompt_loader.load_prompt import load_prompt


async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '召回字段信息'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        context = runtime.context
        embedding_client = context['embedding_client']
        column_qdrant_repository = context['column_qdrant_repository']

        keywords = state['keywords']
        # 1. 使用LLM扩展关键词
        prompt = PromptTemplate(template=load_prompt('extend_keywords_for_column_recall'), input_variables=['query'])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        ret = await chain.ainvoke(input={'query': state['query']})
        keywords.extend(ret)
        keywords = list(set(keywords))
        logger.info(f'【recall_column】 llm extended keywords: {keywords}')
        # 2. 使用扩展后的关键词召回字段信息
        vectors = await embedding_client.aembed_documents(keywords)
        column_id_map = {}
        for vector in vectors:
            column_infos: list[ColumnInfo] = await column_qdrant_repository.column_query(vector)
            for column_info in column_infos:
                if column_info.id not in column_id_map:
                    column_id_map[column_info.id] = column_info
        retrieved_columns: list[str] = list(column_id_map.values())
        logger.info(f'recall column success: {column_id_map.keys()}')
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        return {'retrieved_columns': retrieved_columns}
    except Exception as e:
        logger.error(f'recall_column fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise
