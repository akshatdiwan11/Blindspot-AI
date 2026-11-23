from fastapi import APIRouter

from app.api import datasets, demo, evaluations, health, projects

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(datasets.router)
api_router.include_router(evaluations.router)
api_router.include_router(demo.router)
from app.api import experiments, investigations  # noqa: E402

api_router.include_router(investigations.router)
api_router.include_router(experiments.router)
from app.api import overview, reports  # noqa: E402

api_router.include_router(reports.router)
api_router.include_router(overview.router)
