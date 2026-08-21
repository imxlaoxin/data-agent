import uuid

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from app.api.routes.query_route import query_router
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.context import req_ctx_id_var
from app.core.log import init_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logger()
    embedding_client_manager.init()
    qdrant_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    yield
    await qdrant_client_manager.close()
    await es_client_manager.close()
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()


app = FastAPI(lifespan=lifespan)
app.include_router(query_router)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    request_id = str(uuid.uuid4())
    req_ctx_id_var.set(request_id)
    response = await call_next(request)
    return response


if __name__ == "__main__":
    import uvicorn
    # reload=True 相当于开启了热重载
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)