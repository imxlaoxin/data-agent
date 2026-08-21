"""
python -m module1.module2....
    通过python -m 的方式可以不将当前运行脚本放入环境变量中，而是将当前所处目录加入环境变量中。

(.venv) G:\project\python\AI-Model\project\data-agent>python app\scripts\build_meta_knowledge.py -c .\conf\meta_config.yml
Traceback (most recent call last):
  File "G:\project\python\AI-Model\project\data-agent\app\scripts\build_meta_knowledge.py", line 3, in <module>
    from app.core.log import logger
ModuleNotFoundError: No module named 'app'

(.venv) G:\project\python\AI-Model\project\data-agent>python -m app.scripts.build_meta_knowledge -c .\conf\meta_config.yml
2026-06-06 20:28:16.124 | INFO     | __main__:build:6 - build...

"""
import argparse
import asyncio
from pathlib import Path

from app.core.log import init_logger
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.repositories.qdrant.value_qdrant_repository import ValueQdrantRepository
from app.services.meta_knowledge_service import MetaKnowledgeService
from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.clients.mysql_client_manager import dw_mysql_client_manager
from app.repositories.mysql.dw.dw_mysql_repository import DwMySQLRepository
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository


async def build(config_path: Path):
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()
    async with meta_mysql_client_manager.session_factory() as meta_session, dw_mysql_client_manager.session_factory() as dw_session:
        meta_mysql_repository = MetaMySQLRepository(meta_session)
        dw_mysql_repository = DwMySQLRepository(dw_session)
        column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.qdrant_client)
        value_es_repository = ValueESRepository(es_client_manager.es_client)
        metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.qdrant_client)
        value_qdrant_repository = ValueQdrantRepository(qdrant_client_manager.qdrant_client)
        meta_knowledge_service = MetaKnowledgeService(
            meta_mysql_repository=meta_mysql_repository,
            dw_mysql_repository=dw_mysql_repository,
            column_qdrant_repository=column_qdrant_repository,
            embedding_client=embedding_client_manager.embedding_client,
            value_es_repository=value_es_repository,
            metric_qdrant_repository=metric_qdrant_repository,
            value_qdrant_repository=value_qdrant_repository,
        )
        await meta_knowledge_service.build(config_path)
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()


if __name__ == '__main__':
    init_logger()   # 初始化日志配置
    # argparse:  https://docs.python.org/zh-cn/3/howto/argparse.html
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-c', '--conf')  # -c/--conf 可选参数
    args = arg_parser.parse_args()
    asyncio.run(build(Path(args.conf)))
