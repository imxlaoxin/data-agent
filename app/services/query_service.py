import json
import uuid
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.repositories.qdrant.value_qdrant_repository import ValueQdrantRepository


class QueryService:
    def __init__(
            self,
            column_qdrant_repository: ColumnQdrantRepository,
            metric_qdrant_repository: MetricQdrantRepository,
            value_es_repository: ValueESRepository,
            meta_mysql_repository: MetaMySQLRepository,
            dw_mysql_repository: DwMySQLRepository,
            embedding_client: HuggingFaceEndpointEmbeddings,
            value_qdrant_repository: ValueQdrantRepository,
    ):
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.embedding_client = embedding_client
        self.value_qdrant_repository = value_qdrant_repository


    async def query(self, query: str):
        input = {'query': query}
        context = DataAgentContext(
            embedding_client=self.embedding_client,
            column_qdrant_repository=self.column_qdrant_repository,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
            value_qdrant_repository=self.value_qdrant_repository,
        )
        try:
            async for chunk in graph.astream(input, context=context, stream_mode='custom'):
                # yield f'id: {uuid.uuid4()}\ndata: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n'
                yield f'data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n'
        except Exception as e:
            logger.error(e)
            error = {'type': 'error', 'message': str(e)}
            # yield f'id: {uuid.uuid4()}\ndata: {json.dumps(error, ensure_ascii=False, default=str)}\n\n'
            yield f'data: {json.dumps(error, ensure_ascii=False, default=str)}\n\n'

