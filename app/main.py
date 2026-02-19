import logging
from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import configure_logging, RequestIdFilter
from app.core.middleware import RequestIdMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.ask import router as ask_router
from app.retrieval.index_store import load_index_bundle

configure_logging(settings.log_level)
logging.getLogger().addFilter(RequestIdFilter())

app = FastAPI(title=settings.app_name)

@app.on_event("startup")
def _warmup():
    load_index_bundle()

app.add_middleware(RequestIdMiddleware)

app.include_router(health_router)
app.include_router(ask_router)
