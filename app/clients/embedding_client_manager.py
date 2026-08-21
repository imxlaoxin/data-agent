import asyncio

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.conf.app_config import EmbeddingConfig, app_config


class EmbeddingClientManager:
    def __init__(self, embed_config):
        self.embedding_client: HuggingFaceEndpointEmbeddings | None = None
        self.embedding_config: EmbeddingConfig = embed_config

    def init(self):
        self.embedding_client = HuggingFaceEndpointEmbeddings(
            model=self._get_host_url()
        )

    def _get_host_url(self):
        return f'http://{self.embedding_config.host}:{self.embedding_config.port}'


embedding_client_manager = EmbeddingClientManager(app_config.embedding)

if __name__ == '__main__':
    embedding_client_manager.init()
    client = embedding_client_manager.embedding_client


    async def test():
        text = "What is deep learning?"
        query_result = await client.aembed_query(text)
        print(query_result[:3])


    asyncio.run(test())
