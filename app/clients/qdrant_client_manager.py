import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

from app.conf.app_config import QdrantConfig, app_config


class QdrantClientManager:
    def __init__(self, qdrant_config: QdrantConfig):
        self.qdrant_client: AsyncQdrantClient | None = None
        self.qdrant_config: QdrantConfig = qdrant_config

    def init(self):
        self.qdrant_client = AsyncQdrantClient(url=self._get_host_url())

    async def close(self):
        if self.qdrant_client:
            await self.qdrant_client.close()

    def _get_host_url(self):
        return f'http://{self.qdrant_config.host}:{self.qdrant_config.port}'


qdrant_client_manager = QdrantClientManager(app_config.qdrant)

if __name__ == '__main__':
    qdrant_client_manager.init()
    client = qdrant_client_manager.qdrant_client


    async def test():

        if not await client.collection_exists("test_collection_async"):
            await client.create_collection(
                collection_name="test_collection_async",
                vectors_config=VectorParams(size=4, distance=Distance.DOT),
            )
        operation_info = await client.upsert(
            collection_name="test_collection_async",
            wait=True,
            points=[
                PointStruct(id=1, vector=[0.05, 0.61, 0.76, 0.74], payload={"city": "Berlin"}),
                PointStruct(id=2, vector=[0.19, 0.81, 0.75, 0.11], payload={"city": "London"}),
                PointStruct(id=3, vector=[0.36, 0.55, 0.47, 0.94], payload={"city": "Moscow"}),
                PointStruct(id=4, vector=[0.18, 0.01, 0.85, 0.80], payload={"city": "New York"}),
                PointStruct(id=5, vector=[0.24, 0.18, 0.22, 0.44], payload={"city": "Beijing"}),
                PointStruct(id=6, vector=[0.35, 0.08, 0.11, 0.44], payload={"city": "Mumbai"}),
            ],
        )

        print(operation_info)

        search_result = await client.query_points(
            collection_name="test_collection_async",
            query=[0.2, 0.1, 0.9, 0.7],
            with_payload=True,
            limit=3
        )

        print(search_result.points)

        await qdrant_client_manager.close()


    asyncio.run(test())
