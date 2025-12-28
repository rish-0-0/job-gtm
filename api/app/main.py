from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import root_data, workflows, custom_views

app = FastAPI(
    title="Job GTM Dashboard API",
    description="API for job listings dashboard",
    version="0.1.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(root_data.router, prefix="/api", tags=["root-data"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(custom_views.router, prefix="/api/views", tags=["custom-views"])


@app.get("/")
def root():
    return {"service": "job-gtm-dashboard-api", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from app.config import API_HOST, API_PORT

    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=True)
