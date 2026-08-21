from typing import TypedDict, Annotated
from pydantic import Field

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str


class DBInfoState(TypedDict):
    version: str
    dialect: str


class DataAgentState(TypedDict):
    query: Annotated[str, Field(description='用户输入信息')]
    keywords: Annotated[list[str], Field(description='关键词')]
    retrieved_columns: Annotated[list[ColumnInfo], Field(description='召回字段')]
    retrieved_metrics: Annotated[list[MetricInfo], Field(description='召回指标')]
    retrieved_column_values: Annotated[list[ValueInfo], Field(description='召回字段取值')]
    table_infos: Annotated[list[TableInfoState], Field(description='整合后的表格信息')]
    metric_infos: Annotated[list[TableInfoState], Field(description='整合后的指标信息')]
    date_info: Annotated[DateInfoState, Field(description='日期信息')]
    db_info: Annotated[DBInfoState, Field(description='数据库信息')]
    sql: Annotated[str, Field(description='生成的sql')]
    error: Annotated[str, Field(description='检验sql有误时的错误信息')]
    retry_count: Annotated[int, Field(description='SQL纠错的重试次数')]
