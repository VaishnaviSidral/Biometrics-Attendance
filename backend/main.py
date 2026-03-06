"""
Biometrics Attendance System - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import settings
from database import init_db
from routers import upload, employees, reports, settings as settings_router, auth, employee_attendance, holidays

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Biometrics Attendance System",
    description="HR Attendance Management System with Biometric Data Processing",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(employee_attendance.router, prefix=settings.API_PREFIX)
app.include_router(upload.router, prefix=settings.API_PREFIX)
app.include_router(employees.router, prefix=settings.API_PREFIX)
app.include_router(reports.router, prefix=settings.API_PREFIX)
app.include_router(settings_router.router, prefix=settings.API_PREFIX)
app.include_router(holidays.router, prefix=settings.API_PREFIX)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Biometrics Attendance System API",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
