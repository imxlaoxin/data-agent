from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import DBInfoState


class DwMySQLRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_table_types(self, table_name) -> dict[str, str]:
        # 查询表所有字段信息
        sql = f'show columns from {table_name};'
        res = await self.session.execute(text(sql))
        ret = res.mappings().fetchall()
        return {item['Field']: item['Type'] for item in ret}

    async def get_column_examples_values(self, table_name, column_name, limit=10) -> list[str]:
        # 查询表字段对应值
        sql = f'select distinct {column_name} from {table_name} limit {limit};'
        res = await self.session.execute(text(sql))
        return [item[0] for item in res.fetchall()]

    async def get_all_column_values(self, table_name, column_name) -> list[str]:
        # 查询表字段对应值
        sql = f'select distinct {column_name} from {table_name};'
        res = await self.session.execute(text(sql))
        return [item[0] for item in res.fetchall()]

    async def get_db_info(self):
        sql = "select version();"
        ret = await self.session.execute(text(sql))
        version = ret.scalar().__str__()

        dialect = self.session.bind.dialect.name

        return DBInfoState(version=version, dialect=dialect)

    async def validate_sql(self, sql):
        sql = f'explain {sql}'
        await self.session.execute(text(sql))

    async def execute_sql(self, sql) -> list[dict]:
        ret = await self.session.execute(text(sql))
        return [dict(row_map) for row_map in ret.mappings().fetchall()]
