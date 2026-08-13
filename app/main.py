from fastapi import FastAPI

from app.api.routes import router
from app.database.database import Base, engine


# Create database tables
Base.metadata.create_all(bind=engine)


# Create FastAPI application
app = FastAPI(
    title="AI Content Automation API",
    description="REST API for the AI Content Automation Platform",
    version="1.0.0"
)


# Register API routes
app.include_router(router)


@app.get("/")
def root():
    return {
        "message": "AI Content Automation API is running",
        "status": "online"
    }