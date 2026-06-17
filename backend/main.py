from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routes.dashboard_routes import router as dashboard_router
from backend.services.scheduler import get_scheduler
from backend.utils.logger import logger
from backend.config.settings import settings
import os
import threading


app = FastAPI(
    title="Render Monitor API",
    description="Real-time monitoring system for Render services",
    version="1.0.0"
)


def start_scheduler():
    """Start the scheduler in a background thread."""
    def run_scheduler():
        try:
            scheduler = get_scheduler()
            scheduler.start()
            logger.info("Scheduler thread started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler thread: {str(e)}")
    
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    return thread


@app.on_event("startup")
async def startup_event():
    """Initialize app on startup."""
    logger.info("=" * 50)
    logger.info("Starting Render Monitor (FastAPI)")
    logger.info("=" * 50)
    logger.info(f"FastAPI running on {settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    start_scheduler()
    logger.info("Background scheduler initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Render Monitor")
    scheduler = get_scheduler()
    if scheduler.is_running:
        scheduler.stop()


@app.get("/")
async def serve_index():
    """Serve main dashboard HTML."""
    frontend_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'frontend',
        'index.html'
    )
    return FileResponse(frontend_path)


@app.get("/api/info")
async def api_info():
    """API information endpoint."""
    return {
        'name': 'Render Monitor API',
        'version': '1.0.0',
        'endpoints': {
            'status': 'GET /api/status',
            'history': 'GET /api/history',
            'services_health': 'GET /api/services/health',
            'render_logs': 'GET /api/render-logs',
            'health': 'GET /api/health',
            'manual_check': 'POST /api/monitor/check',
            'clear_logs': 'POST /api/monitor/clear-logs'
        }
    }


app.include_router(dashboard_router)


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
if os.path.exists(frontend_dir):
    app.mount('/static', StaticFiles(directory=frontend_dir), name='static')
    app.mount('/css', StaticFiles(directory=os.path.join(frontend_dir, 'css')), name='css')
    app.mount('/js', StaticFiles(directory=os.path.join(frontend_dir, 'js')), name='js')
    if os.path.exists(os.path.join(frontend_dir, 'assets')):
        app.mount('/assets', StaticFiles(directory=os.path.join(frontend_dir, 'assets')), name='assets')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.FASTAPI_HOST,
        port=settings.FASTAPI_PORT,
        debug=settings.DEBUG,
        log_level="info"
    )
