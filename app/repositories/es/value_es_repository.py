from dataclasses import asdict

from elasticsearch import AsyncElasticsearch

from app.entities.value_info import ValueInfo


class ValueESRepository:
    __index_name__ = 'value_index'
    __index_mappings__ = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
            "column_id": {"type": "keyword"}
        }
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def _check_index_exists(self):
        if not await self.client.indices.exists(index=self.__index_name__):
            await self.client.indices.create(
                index=self.__index_name__,
                mappings=self.__index_mappings__
            )

    async def save_value_infos(self, value_infos: list[ValueInfo], batch_size=100):
        await self._check_index_exists()
        operations: list[dict] = []
        for value_info in value_infos:
            operations.append({
                "index": {
                    "_index": self.__index_name__,
                    "_id": value_info.id  # 显式增加 "_id" 字段映射，依赖其实现覆盖更新
                }
            })
            operations.append({
                **asdict(value_info)
            })
        for i in range(0, len(operations), batch_size):
            await self.client.bulk(
                operations=operations[i:i + batch_size],
            )

    async def value_query(self, keyword, score_threshold: float = 0.5, limit: int = 5) -> list[ValueInfo]:
        resp = await self.client.search(
            index=self.__index_name__,
            query={
                "match": {
                    "value": {
                        "query": keyword,
                    }
                },
            },
            min_score=score_threshold,
            size=limit,
        )
        return [ValueInfo(**hit['_source']) for hit in resp['hits']['hits']]

