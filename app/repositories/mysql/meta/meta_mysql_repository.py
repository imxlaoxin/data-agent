from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.models.column_info import ColumnInfoMySQL
from app.models.table_info import TableInfoMySQL
from app.repositories.mysql.meta.mapppers.column_info_mapper import ColumnInfoMapper
from app.repositories.mysql.meta.mapppers.column_metric_mapper import ColumnMetricMapper
from app.repositories.mysql.meta.mapppers.metric_info_mapper import MetricInfoMapper
from app.repositories.mysql.meta.mapppers.table_info_mapper import TableInfoMapper

"""
add_all:
    在 SQLAlchemy 中，add_all 只是将一批对象标记为“新建（New）”并挂载到当前会话（Session）中。
当提交（commit）或刷新（flush）时，SQLAlchemy 会将它们打包成批量 INSERT 语句发给数据库，性能极高。
merge:
    merge 的底层逻辑：merge 是一个非常重的操作。当你对一个对象调用 merge 时，SQLAlchemy 会先向数据库发送一条 SELECT 语句来查询这个主键对应的记录存不存在。  
如果存在，它会将新对象的值拷贝过去，并生成一条 UPDATE 语句。如果不存在，它才会生成一条 INSERT 语句。这意味着，如果你有 1000 个字段要同步，merge 会先产生 1000 次 SELECT 查询（即典型的 N+1 查询问题），这在网络 I/O 和数据库 CPU 消耗上都是灾难性的。
"""
class MetaMySQLRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_table_infos(self, table_info_list: list[TableInfo]):
        # self.session.add_all([TableInfoMapper.to_model(table_info) for table_info in table_info_list])
        for table_info in table_info_list:
            await self.session.merge(TableInfoMapper.to_model(table_info))

    async def save_column_infos(self, column_info_list: list[ColumnInfo]):
        # self.session.add_all([ColumnInfoMapper.to_model(column_info) for column_info in column_info_list])
        for column_info in column_info_list:
            await self.session.merge(ColumnInfoMapper.to_model(column_info))

    async def save_metric_infos(self, metric_info_list: list[MetricInfo]):
        # self.session.add_all([MetricInfoMapper.to_model(metric_info) for metric_info in metric_info_list])
        for metric_info in metric_info_list:
            await self.session.merge(MetricInfoMapper.to_model(metric_info))

    async def save_column_metric_infos(self, column_metric_list: list[ColumnMetric]):
        # self.session.add_all([ColumnMetricMapper.to_model(column_metric) for column_metric in column_metric_list])
        for column_metric in column_metric_list:
            await self.session.merge(ColumnMetricMapper.to_model(column_metric))

    async def get_column_info_by_id(self, column_id) -> ColumnInfo | None:
        column_info_mysql: ColumnInfoMySQL | None = await self.session.get(ColumnInfoMySQL, column_id)
        if column_info_mysql:
            return ColumnInfoMapper.to_entity(column_info_mysql)
        else:
            return None

    async def get_table_info_by_id(self, table_id) -> TableInfo | None:
        table_info_mysql: TableInfoMySQL | None = await self.session.get(TableInfoMySQL, table_id)
        if table_info_mysql:
            return TableInfoMapper.to_entity(table_info_mysql)
        else:
            return None

    async def get_primary_and_foreign_key_column_by_table_id(self, table_id):
        sql = "select * from column_info where table_id = :table_id and role in ('primary_key', 'foreign_key')"
        ret = await self.session.execute(text(sql), {"table_id": table_id})
        return [ColumnInfo(**dict(ret)) for ret in ret.mappings().fetchall()]
