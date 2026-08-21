import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker

from app.conf.app_config import DbConfig, app_config


class MySQLClientManager:
    def __init__(self, config: DbConfig):
        self.engine: AsyncEngine | None = None
        self.db_config: DbConfig = config
        self.session_factory: async_sessionmaker | None = None

    def init(self):
        self.engine = create_async_engine(self._get_host_url(), pool_pre_ping=True, pool_size=10)
        self.session_factory = async_sessionmaker(self.engine, autoflush=True, expire_on_commit=False)

    def _get_host_url(self):
        return f"mysql+asyncmy://{self.db_config.user}:{self.db_config.password}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}?charset=utf8mb4"

    async def close(self):
        if self.engine:
            await self.engine.dispose()


dw_mysql_client_manager = MySQLClientManager(app_config.db_dw)
meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)

if __name__ == '__main__':
    dw_mysql_client_manager.init()
    async def test():
        # auto_flush: 保证更新后，数据库同步更新; expire_on_commit: 异步需要设置为False
        # async with AsyncSession(engine, auto_flush=True, expire_on_commit=False) as session:
        async with dw_mysql_client_manager.session_factory() as session:
            sql = "select * from dw.fact_order limit 10"
            ret = await session.execute(text(sql))  # text方法将sql str转为可执行的sql
            fetch_ret = ret.mappings().fetchall()   # mappings将rows元组类型转为dict字典类型，可以直接通过字段取值
            print(type(fetch_ret))
            print(type(fetch_ret[0]))
            print(fetch_ret[0])
            print(fetch_ret[0]['order_id'])

        await dw_mysql_client_manager.close()


    asyncio.run(test())