from dataclasses import dataclass


"""
index_type详解:
1. none: 默认值，不创建索引
2. es: 创建es索引 
    此类字段基数极大（动辄上万甚至百万），且用户查询时通常是精准的专有名词，不需要（也很难）进行语义发散。
3. vector: 创建向量索引 
    此类字段基数极小（通常在几个到几十个之间），是典型的业务枚举值。用户提问往往极其口语化，极其需要语义对齐能力。
4. both: 同时创建向量索引和es索引
    此类字段基数中等（几十到几百），且既可能遭遇同义词/口语化挑战，又存在专有名词精确匹配的需求。双路构建能保障极高的召回率。
"""
@dataclass
class ColumnConfig:
    name: str
    role: str
    description: str
    alias: list[str]
    # sync: bool
    index_type: str | None = 'none'


@dataclass
class TableConfig:
    name: str
    role: str
    description: str
    columns: list[ColumnConfig]


@dataclass
class MetricConfig:
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


@dataclass
class MetaConfig:
    tables: list[TableConfig] | None = None
    metrics: list[MetricConfig] | None = None
