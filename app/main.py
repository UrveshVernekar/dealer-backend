from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.init_db import init_db
from app.routers.auth import router as auth_router
from app.routers.schemes import router as schemes_router
from app.routers.data_import import router as import_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database and seed initial values
    init_db()
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(schemes_router)
app.include_router(import_router)


@app.get("/")
def root():
    return {"message": f"{settings.PROJECT_NAME} is running"}
