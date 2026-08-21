import uuid
from dataclasses import asdict
from pathlib import Path
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf
from qdrant_client.models import PointStruct
from app.core.log import logger
from app.conf.meta_config import MetaConfig
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySQLRepository
from app.entities.column_info import ColumnInfo
from app.entities.table_info import TableInfo
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.entities.value_info import ValueInfo
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.repositories.qdrant.value_qdrant_repository import ValueQdrantRepository


class MetaKnowledgeService:
    def __init__(
            self,
            meta_mysql_repository: MetaMySQLRepository,
            dw_mysql_repository: DwMySQLRepository,
            column_qdrant_repository: ColumnQdrantRepository,
            embedding_client: HuggingFaceEndpointEmbeddings,
            value_es_repository: ValueESRepository,
            metric_qdrant_repository: MetricQdrantRepository,
            value_qdrant_repository: ValueQdrantRepository,
    ):
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.embedding_client = embedding_client
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_qdrant_repository = value_qdrant_repository

    async def _save_table_and_column_info_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfo]:
        table_info_list: list[TableInfo] = []
        column_info_list: list[ColumnInfo] = []
        for table in meta_config.tables:
            table_info = TableInfo(id=table.name, name=table.name, role=table.role,
                                   description=table.description)
            table_types = await self.dw_mysql_repository.get_table_types(table.name)
            table_info_list.append(table_info)
            for column in table.columns:
                examples = await self.dw_mysql_repository.get_column_examples_values(table.name, column.name)
                column_info = ColumnInfo(
                    id=f'{table.name}.{column.name}',
                    name=column.name,
                    type=table_types[column.name],
                    role=column.role,
                    examples=examples,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name
                )
                column_info_list.append(column_info)

        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_table_infos(table_info_list)
            await self.meta_mysql_repository.save_column_infos(column_info_list)
        logger.info('表，字段同步数据库完成.')
        return column_info_list

    async def _save_column_info_to_qdrant(self, column_info_list: list[ColumnInfo]):
        temp_points: list[dict] = []
        embedding_text_list: list[str] = []
        for column_info in column_info_list:
            payload = asdict(column_info)
            name_point = {
                'id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{column_info.id}_name")),
                'payload': payload,
            }
            temp_points.append(name_point)
            embedding_text_list.append(column_info.name)
            description_point = {
                'id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{column_info.id}_desc")),
                'payload': payload,
            }
            temp_points.append(description_point)
            embedding_text_list.append(column_info.description)
            for alias_item in column_info.alias:
                alias_point = {
                    'id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{column_info.id}_alias_{alias_item}")),
                    'payload': payload,
                }
                temp_points.append(alias_point)
                embedding_text_list.append(alias_item)

        vectors: list[list[float]] = []
        embedding_batch_size = 10
        for i in range(0, len(embedding_text_list), embedding_batch_size):
            batch_vector: list[list[float]] = await self.embedding_client.aembed_documents(
                embedding_text_list[i:i + embedding_batch_size])
            vectors.extend(batch_vector)

        points: list[PointStruct] = [PointStruct(id=temp_point['id'], vector=vector, payload=temp_point['payload'])
                                     for temp_point, vector in zip(temp_points, vectors)]
        await self.column_qdrant_repository.save_column_points(points)
        logger.info(f'维度字段向量索引构建完成.')

    async def _save_value_into_to_es(self, meta_config: MetaConfig):
        value_infos: list[ValueInfo] = []
        for table in meta_config.tables:
            for column in table.columns:
                # if column.sync:
                index_type = getattr(column, 'index_type', 'none')
                if index_type in ['es', 'both']:
                    cur_column_values = await self.dw_mysql_repository.get_all_column_values(table.name, column.name)
                    cur_value_infos = [ValueInfo(
                        id=f'{table.name}.{column.name}.{value}',
                        value=value,
                        column_id=f'{table.name}.{column.name}',
                    ) for value in cur_column_values if value is not None]
                    value_infos.extend(cur_value_infos)
        if value_infos:
            await self.value_es_repository.save_value_infos(value_infos)
            logger.info(f'指定字段对应值 ES 全文索引构建完成.')

    async def _save_value_info_to_qdrant(self, meta_config: MetaConfig):
        """[新增] 将指定维度的具体值同步到 Qdrant"""
        temp_points: list[dict] = []
        embedding_text_list: list[str] = []
        for table in meta_config.tables:
            for column in table.columns:
                index_type = getattr(column, 'index_type', 'none')
                if index_type in ['vector', 'both']:
                    cur_column_values = await self.dw_mysql_repository.get_all_column_values(table.name, column.name)
                    for value in cur_column_values:
                        if value is None:
                            continue
                        value_id = f'{table.name}.{column.name}.{value}'
                        payload = {
                            'id': value_id,
                            'value': str(value),
                            'column_id': f'{table.name}.{column.name}',
                        }
                        # 使用确定的 uuid5 生成 ID，避免重复运行产生脏数据
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, value_id))
                        temp_points.append({
                            'id': point_id,
                            'payload': payload,
                        })
                        embedding_text_list.append(str(value))

        if not embedding_text_list:
            return

        vectors: list[list[float]] = []
        embedding_batch_size = 10
        for i in range(0, len(embedding_text_list), embedding_batch_size):
            batch_vector: list[list[float]] = await self.embedding_client.aembed_documents(
                embedding_text_list[i:i + embedding_batch_size])
            vectors.extend(batch_vector)

        points: list[PointStruct] = [PointStruct(id=temp_point['id'], vector=vector, payload=temp_point['payload'])
                                     for temp_point, vector in zip(temp_points, vectors)]
        await self.value_qdrant_repository.save_value_points(points)
        logger.info(f'指定字段对应值 Qdrant 向量索引构建完成.')

    async def _save_metric_and_column_metric_to_meta_db(self, meta_config: MetaConfig):
        metric_info_list: list[MetricInfo] = []
        column_metric_list: list[ColumnMetric] = []
        for metric in meta_config.metrics:
            metric_info = MetricInfo(id=metric.name, name=metric.name,
                                     description=metric.description, relevant_columns=metric.relevant_columns,
                                     alias=metric.alias)
            metric_info_list.append(metric_info)
            for column in metric.relevant_columns:
                column_metric_info = ColumnMetric(column_id=column, metric_id=metric.name)
                column_metric_list.append(column_metric_info)

        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_metric_infos(metric_info_list)
            await self.meta_mysql_repository.save_column_metric_infos(column_metric_list)
        logger.info('指标同步数据库完成.')
        return metric_info_list

    async def _save_metric_info_to_qdrant(self, metric_info_list: list[MetricInfo]):
        temp_points: list[dict] = []
        embedding_text_list: list[str] = []
        for metric_info in metric_info_list:
            payload = asdict(metric_info)
            name_point = {
                'id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{metric_info.id}_name")),
                'payload': payload,
            }
            temp_points.append(name_point)
            embedding_text_list.append(metric_info.name)
            description_point = {
                'id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{metric_info.id}_desc")),
                'payload': payload,
            }
            temp_points.append(description_point)
            embedding_text_list.append(metric_info.description)
            for alias_item in metric_info.alias:
                alias_point = {
                    'id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{metric_info.id}_alias_{alias_item}")),
                    'payload': payload,
                }
                temp_points.append(alias_point)
                embedding_text_list.append(alias_item)

        vectors: list[list[float]] = []
        embedding_batch_size = 10
        for i in range(0, len(embedding_text_list), embedding_batch_size):
            batch_vector: list[list[float]] = await self.embedding_client.aembed_documents(
                embedding_text_list[i:i + embedding_batch_size])
            vectors.extend(batch_vector)

        points: list[PointStruct] = [PointStruct(id=temp_point['id'], vector=vector, payload=temp_point['payload'])
                                     for temp_point, vector in zip(temp_points, vectors)]
        await self.metric_qdrant_repository.save_metric_points(points)
        logger.info(f'指标向量索引构建完成.')

    async def build(self, config_path: Path):
        # 1. 从配置文件中加载配置
        config = OmegaConf.load(config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, config))
        # 2. 根据配置更新元数据库表
        if meta_config.tables:
            # 同步表信息
            # 2.1 将表，字段同步到元数据库中
            column_info_list = await self._save_table_and_column_info_to_meta_db(meta_config)
            # 2.2 为维度字段建立向量索引
            await self._save_column_info_to_qdrant(column_info_list)
            # 2.3 为指定字段建立全文/向量索引
            await self._save_value_into_to_es(meta_config)
            await self._save_value_info_to_qdrant(meta_config)

        # 3. 根据配置更新元数据指标
        if meta_config.metrics:
            # 同步指标信息
            # 2.1 将指标同步到元数据库中
            metric_info_list = await self._save_metric_and_column_metric_to_meta_db(meta_config)
            # 2.2 为指标建立向量索引
            await self._save_metric_info_to_qdrant(metric_info_list)
