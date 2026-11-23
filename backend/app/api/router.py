from fastapi import APIRouter

from app.api import datasets, demo, evaluations, health, projects

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(datasets.router)
api_router.include_router(evaluations.router)
api_router.include_router(demo.router)
