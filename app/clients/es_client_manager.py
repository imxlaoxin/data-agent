import asyncio

from elasticsearch import AsyncElasticsearch

from app.conf.app_config import ESConfig, app_config


class ESClientManager:
    def __init__(self, es_config: ESConfig):
        self.es_client: AsyncElasticsearch | None = None
        self.es_config: ESConfig = es_config

    def init(self):
        self.es_client = AsyncElasticsearch(hosts=[self._get_host_url()])

    async def close(self):
        if self.es_client:
            await self.es_client.close()

    def _get_host_url(self):
        return f'http://{self.es_config.host}:{self.es_config.port}'


es_client_manager = ESClientManager(app_config.es)

if __name__ == '__main__':
    es_client_manager.init()
    client = es_client_manager.es_client


    async def test():
        if not await client.indices.exists(index='books'):
            resp = await client.indices.create(
                index="books",
            )
            print(resp)
        resp = await client.index(
            index="books",
            document={
                "name": "Snow Crash",
                "author": "Neal Stephenson",
                "release_date": "1992-06-01",
                "page_count": 470
            },
        )
        print(resp)

        resp = await client.search(
            index="books",
        )
        print(resp)

        await es_client_manager.close()


    asyncio.run(test())
