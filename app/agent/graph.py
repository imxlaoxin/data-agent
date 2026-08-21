import asyncio

from langgraph.graph import StateGraph, START, END
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.execute_sql import execute_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.merge_retrieved import merge_retrieved
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_column_value import recall_column_value
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.validate_sql import validate_sql
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.repositories.qdrant.value_qdrant_repository import ValueQdrantRepository

graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

# 添加节点
graph_builder.add_node("extract_keywords", extract_keywords)
graph_builder.add_node("recall_column", recall_column)
graph_builder.add_node("recall_column_value", recall_column_value)
graph_builder.add_node("recall_metric", recall_metric)
graph_builder.add_node("merge_retrieved", merge_retrieved)
graph_builder.add_node("filter_metric", filter_metric)
graph_builder.add_node("filter_table", filter_table)
graph_builder.add_node("add_extra_context", add_extra_context)
graph_builder.add_node("generate_sql", generate_sql)
graph_builder.add_node("validate_sql", validate_sql)
graph_builder.add_node("correct_sql", correct_sql)
graph_builder.add_node("execute_sql", execute_sql)

# 添加关系
graph_builder.add_edge(START, "extract_keywords")
graph_builder.add_edge("extract_keywords", "recall_column")
graph_builder.add_edge("extract_keywords", "recall_metric")
graph_builder.add_edge("extract_keywords", "recall_column_value")
graph_builder.add_edge("recall_column", "merge_retrieved")
graph_builder.add_edge("recall_metric", "merge_retrieved")
graph_builder.add_edge("recall_column_value", "merge_retrieved")
graph_builder.add_edge("merge_retrieved", "filter_table")
graph_builder.add_edge("merge_retrieved", "filter_metric")
graph_builder.add_edge("filter_table", "add_extra_context")
graph_builder.add_edge("filter_metric", "add_extra_context")
graph_builder.add_edge("add_extra_context", "generate_sql")
graph_builder.add_edge("generate_sql", "validate_sql")

"""

"""
def route_after_validation(state: DataAgentState) -> str:
    """根据校验结果和重试次数决定去向"""
    error = state.get('error')
    retry_count = state.get('retry_count', 0)

    if not error:
        # 如果没有报错，直接去执行
        return 'execute_sql'

    if retry_count >= 3:
        # 如果重试次数超过限制（例如 3 次）依然报错，强行终止，防止死循环
        logger.error(f"SQL 纠错次数达到上限({retry_count}次)，终止执行。最后一次错误: {error}")
        return 'end'

    # 如果有报错且在重试次数内，去纠错
    return 'correct_sql'

graph_builder.add_conditional_edges('validate_sql',
                                    route_after_validation,
                                    path_map={'execute_sql': 'execute_sql', 'correct_sql': 'correct_sql', 'end': END}
                                    )
graph_builder.add_edge('correct_sql', 'validate_sql')
graph_builder.add_edge('execute_sql', END)


# 编译图
graph = graph_builder.compile()

# print(graph.get_graph().draw_mermaid())
if __name__ == '__main__':
    async def test():
        # 显式初始化日志
        from app.core.log import init_logger
        init_logger()

        embedding_client_manager.init()
        qdrant_client_manager.init()
        es_client_manager.init()
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()

        async with meta_mysql_client_manager.session_factory() as meta_session, dw_mysql_client_manager.session_factory() as dw_session:
            column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.qdrant_client)
            metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.qdrant_client)
            value_qdrant_repository = ValueQdrantRepository(qdrant_client_manager.qdrant_client)
            value_es_repository = ValueESRepository(es_client_manager.es_client)
            meta_mysql_repository = MetaMySQLRepository(meta_session)
            dw_mysql_repository = DwMySQLRepository(dw_session)

            input = {'query': '统计一下华北地区的销售总额'}
            context = DataAgentContext(
                embedding_client=embedding_client_manager.embedding_client,
                column_qdrant_repository=column_qdrant_repository,
                metric_qdrant_repository=metric_qdrant_repository,
                value_es_repository=value_es_repository,
                meta_mysql_repository=meta_mysql_repository,
                dw_mysql_repository=dw_mysql_repository,
                value_qdrant_repository=value_qdrant_repository
            )
            async for chunk in graph.astream(input, context=context, stream_mode='custom'):
                print(chunk)

            await qdrant_client_manager.close()
            await es_client_manager.close()
            await meta_mysql_client_manager.close()
            await dw_mysql_client_manager.close()

    asyncio.run(test())