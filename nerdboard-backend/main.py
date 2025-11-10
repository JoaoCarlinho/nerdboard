"""
NerdBoard Backend API Server

FastAPI application for AI-powered operations intelligence platform.
Serves predictions, dashboard data, and simulation controls.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime
import time

from app.api.routes import health, capacity, quality, simulation, predictions, dashboard
from app.services.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting NerdBoard API server...")

    # Start background scheduler
    start_scheduler()
    logger.info("Background scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down NerdBoard API server...")
    stop_scheduler()
    logger.info("Background scheduler stopped")


# Create FastAPI application
app = FastAPI(
    title="NerdBoard API",
    description="AI-Powered Operations Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)


# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Log request
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration_ms:.2f}ms"
    )

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
                "details": str(exc) if app.debug else None
            }
        }
    )


# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns server status and version information.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "nerdboard-api"
    }


# Include routers
app.include_router(health.router)
app.include_router(predictions.router)
app.include_router(dashboard.router)
app.include_router(capacity.router)
app.include_router(quality.router)
app.include_router(simulation.router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root endpoint"""
    return {
        "name": "NerdBoard API",
        "version": "1.0.0",
        "description": "AI-Powered Operations Intelligence Platform",
        "docs": "/api/docs",
        "health": "/health"
    }


# Admin endpoint to load demo data
@app.post("/admin/load-demo", tags=["Admin"])
async def load_demo_data():
    """Load demo data into the database (physics_shortage scenario)"""
    try:
        import subprocess
        logger.info("Loading demo data...")
        result = subprocess.run(
            ["python3", "-m", "app.scripts.load_demo", "--scenario", "physics_shortage"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            return {"status": "success", "message": "Demo data loaded successfully"}
        else:
            logger.error(f"Failed to load demo data: {result.stderr}")
            return {"status": "error", "message": result.stderr}
    except Exception as e:
        logger.error(f"Error loading demo data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
