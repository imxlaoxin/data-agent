from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from app.conf.app_config import app_config
from app.entities.value_info import ValueInfo

class ValueQdrantRepository:
    __collection_name__ = 'value_collection'

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def _check_exist_value_collection(self):
        """检查字段值集合是否存在"""
        if not await self.client.collection_exists(self.__collection_name__):
            await self.client.create_collection(
                collection_name=self.__collection_name__,
                vectors_config=VectorParams(
                    size=app_config.qdrant.embedding_size,
                    distance=Distance.DOT
                ))

    async def save_value_points(self, points: list[PointStruct], save_batch_size: int = 50):
        """批量保存字段值向量"""
        await self._check_exist_value_collection()
        for i in range(0, len(points), save_batch_size):
            await self.client.upsert(
                collection_name=self.__collection_name__,
                points=points[i:i + save_batch_size],
            )

    async def value_query(self, vector, score_threshold: float = 0.5, limit: int = 5) -> list[ValueInfo]:
        """通过向量查询字段值"""
        search_result = await self.client.query_points(
            collection_name=self.__collection_name__,
            query=vector,
            limit=limit,
            score_threshold=score_threshold,
        )
        # 解析返回为 ValueInfo 实体
        return [ValueInfo(**point.payload) for point in search_result.points]