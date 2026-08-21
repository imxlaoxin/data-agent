import json
import os
import re
import time

from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, ColumnInfoState, TableInfoState, MetricInfoState
from langgraph.runtime import Runtime

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository


async def merge_retrieved(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '合并召回信息'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        retrieved_columns: list[ColumnInfo] = state['retrieved_columns']
        retrieved_metrics: list[MetricInfo] = state['retrieved_metrics']
        retrieved_column_values: list[ValueInfo] = state['retrieved_column_values']

        context = runtime.context
        meta_mysql_repository: MetaMySQLRepository = context['meta_mysql_repository']

        # 1. 整合表格信息
        # 1.1 将指标信息中涉及字段加入字段信息中
        retrieved_columns_map: dict[str, ColumnInfo] = {retrieved_column.id: retrieved_column for retrieved_column in retrieved_columns}
        for retrieved_metric in retrieved_metrics:
            for relevant_column in retrieved_metric.relevant_columns:
                # relevant_column为id，str类型
                if relevant_column not in retrieved_columns_map:
                    relevant_column_info: ColumnInfo | None = await meta_mysql_repository.get_column_info_by_id(relevant_column)
                    if relevant_column_info:
                        retrieved_columns_map[relevant_column] = relevant_column_info
        # 1.2 将召回字段取值追加到字段信息的examples中(在索引阶段已经放入一些example了)
        for retrieved_column_value in retrieved_column_values:
            column_id = retrieved_column_value.column_id
            value = retrieved_column_value.value
            if column_id not in retrieved_columns_map:
                new_column_info: ColumnInfo | None = await meta_mysql_repository.get_column_info_by_id(column_id)
                if new_column_info:
                    retrieved_columns_map[column_id] = new_column_info
            if value not in retrieved_columns_map[column_id].examples:
                retrieved_columns_map[column_id].examples.insert(0, value)
                # retrieved_columns_map[column_id].examples.append(value)

        # 1.3 强制为每个表添加主外键字段
        table_id_to_columns_map: dict[str, list[ColumnInfo]] = {}
        for column in retrieved_columns_map.values():
            table_id = column.table_id
            if table_id not in table_id_to_columns_map:
                table_id_to_columns_map[table_id] = []
            table_id_to_columns_map[table_id].append(column)

        for table_id in table_id_to_columns_map:
            # 根据table_id查询表的主外键对应的相关字段
            key_columns: list[ColumnInfo] = await meta_mysql_repository.get_primary_and_foreign_key_column_by_table_id(table_id)
            existed_column_ids = [column.id for column in table_id_to_columns_map[table_id]]
            for column_info in key_columns:
                if column_info.id not in existed_column_ids:
                    table_id_to_columns_map[table_id].append(column_info)

        # 1.4 整理字段信息为指定格式
        table_infos: list[TableInfoState] = []
        for table_id, columns in table_id_to_columns_map.items():
            table_info: TableInfo | None = await meta_mysql_repository.get_table_info_by_id(table_id)
            columns = [ColumnInfoState(
                name=column.name,
                type=column.type,
                role=column.role,
                examples=column.examples,
                description=column.description,
                alias=column.alias
            ) for column in columns]
            table_info_state: TableInfoState = TableInfoState(
                name=table_info.name,
                role=table_info.role,
                description=table_info.description,
                columns=columns,
            )
            table_infos.append(table_info_state)

        # 2. 整合指标信息
        metric_infos: list[MetricInfoState] = [MetricInfoState(
            name=retrieved_metric.name,
            description=retrieved_metric.description,
            relevant_columns=retrieved_metric.relevant_columns,
            alias=retrieved_metric.alias
        ) for retrieved_metric in retrieved_metrics]

        # 用于调试，观察效果
        query = state['query']
        save_dir = get_safe_dir_name(query)
        os.makedirs(save_dir, exist_ok=True)
        with open(os.path.join(save_dir, 'table_infos.json'), 'w', encoding='utf-8') as f:
            json.dump(table_infos, f, ensure_ascii=False, indent=2)
        with open(os.path.join(save_dir, 'metric_infos.json'), 'w', encoding='utf-8') as f:
            json.dump(metric_infos, f, ensure_ascii=False, indent=2)

        logger.info(f'merge_retrieved success: {len(table_infos)} tables, {len(metric_infos)} metrics')
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        return {'table_infos': table_infos, 'metric_infos': metric_infos}
    except Exception as e:
        logger.error(f'merge_retrieved fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise


def get_safe_dir_name(query: str) -> str:
    # 1. 替换非法路径字符（/ \ : * ? " < > |）为下划线
    clean_query = re.sub(r'[\\/:*?"<>|]', '_', query)
    # 2. 去除前后空格并截取前 30 个字符，防止路径过长
    clean_query = clean_query.strip()[:30]
    # 3. 拼接时间戳（精确到秒），避免覆盖
    # timestamp = time.strftime('%Y%m%d_%H%M%S')
    timestamp = time.strftime('%Y%m%d_%H%M')

    return f'temp_debug/{clean_query}_{timestamp}'