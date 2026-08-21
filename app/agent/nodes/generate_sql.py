import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from loguru import logger

from app.agent.context import DataAgentContext
from app.agent.llm.llm import llm
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.prompt_loader.load_prompt import load_prompt


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]) -> DataAgentState:
    writer = runtime.stream_writer
    step = '生成SQL'
    writer({'type': 'progress', 'step': step, 'status': 'running'})

    try:
        prompt = PromptTemplate(template=load_prompt('generate_sql'), input_variables=[
            'table_infos', 'metric_infos', 'date_info', 'db_info', 'query'
        ])
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        sql: str = await chain.ainvoke({
            'table_infos': yaml.dump(state['table_infos'], allow_unicode=True, sort_keys=False),
            'metric_infos': yaml.dump(state['metric_infos'], allow_unicode=True, sort_keys=False),
            'date_info': yaml.dump(state['date_info'], allow_unicode=True, sort_keys=False),
            'db_info': yaml.dump(state['db_info'], allow_unicode=True, sort_keys=False),
            'query': state['query'],
        })

        logger.info(f'generate_sql success: {sql}')
        writer({'type': 'progress', 'step': step, 'status': 'success'})
        return {'sql': sql}
    except Exception as e:
        logger.error(f'generate_sql fail: {str(e)}')
        writer({'type': 'progress', 'step': step, 'status': 'error'})
        raise



"""
测试：
# 统计一下上个月 Apple 产品的成交总额。
SELECT SUM(t1.order_amount) AS GMV
FROM fact_order t1
JOIN dim_product t2 ON t1.product_id = t2.product_id
JOIN dim_date t3 ON t1.date_id = t3.date_id
WHERE t3.year = 2025 AND t3.month = 1 AND t2.brand = '苹果';

# 我们店里衣服相关的平均客单价是多少？
SELECT AVG(fact_order.order_quantity) AS AOV
FROM fact_order
JOIN dim_product ON fact_order.product_id = dim_product.product_id
WHERE dim_product.category = '服饰';

# 大家平时买吃的喝的，一共花了多少钱？
SELECT SUM(fact_order.order_amount) AS GMV FROM fact_order;

# 江浙沪一带的总收入有多少？
SELECT SUM(t2.order_amount) AS total_income
FROM dim_region t1
JOIN fact_order t2 ON t1.region_id = t2.region_id
WHERE t1.province IN ('浙江省', '上海市');

# 看看妹子们主要买了些什么类目的商品？
SELECT p.category, COUNT(*) AS cnt
FROM fact_order o
JOIN dim_product p ON o.product_id = p.product_id
JOIN dim_customer c ON o.customer_id = c.customer_id
WHERE c.gender = '女'
GROUP BY p.category
ORDER BY cnt DESC;

# 男性同胞的购买力（总金额）如何？
SELECT SUM(t1.order_amount) AS total_amount
FROM fact_order t1
INNER JOIN dim_customer t2 ON t1.customer_id = t2.customer_id
WHERE t2.gender = '男'

"""