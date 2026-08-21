from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from app.conf.app_config import app_config
from app.entities.metric_info import MetricInfo


class MetricQdrantRepository:
    __collection_name__ = 'metric_collection'

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def _check_exist_column_collection(self):
        """ 检查指标集合是否存在"""
        if not await self.client.collection_exists(self.__collection_name__):
            await self.client.create_collection(
                collection_name=self.__collection_name__,
                vectors_config=VectorParams(
                    size=app_config.qdrant.embedding_size,
                    distance=Distance.DOT
                ))

    async def save_metric_points(self, points: list[PointStruct], save_batch_size: int = 20):
        """
        批量保存向量
        :param points:
        :param save_batch_size:
        :return:
        """
        await self._check_exist_column_collection()

        for i in range(0, len(points), save_batch_size):
            await self.client.upsert(
                collection_name=self.__collection_name__,
                points=points[i:i + save_batch_size],
            )

    async def metric_query(self, vector, score_threshold: float = 0.5, limit: int = 5) -> list[MetricInfo]:
        search_result = await self.client.query_points(
            collection_name=self.__collection_name__,
            query=vector,
            limit=limit,
            score_threshold=score_threshold,
        )
        return [MetricInfo(**point.payload) for point in search_result.points]

