"""
Waybern Mews OS — main application entry point.

This file creates the FastAPI app, registers all routes, and handles
startup tasks (database initialisation). All future module routers
are imported and registered here.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
load_dotenv()  # Load GROQ_API_KEY and any other secrets from .env

from app.database import init_db
from app.routers import units as units_router
from app.routers import meter_readings as meter_readings_router
from app.routers import coj_invoices as coj_invoices_router
from app.routers import complex_info as complex_info_router
from app.routers import insurance as insurance_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once on startup: initialises the database."""
    init_db()
    yield


app = FastAPI(title="Waybern Mews OS", lifespan=lifespan)

# Serve files from the /static directory (CSS, images, etc. added in future)
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static"
)

# Point Jinja2 at the templates directory
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "app", "templates")
)

# Register module routers
app.include_router(units_router.router)
app.include_router(meter_readings_router.router)
app.include_router(coj_invoices_router.router)
app.include_router(complex_info_router.router)
app.include_router(insurance_router.router)


@app.get("/")
async def dashboard(request: Request):
    """Renders the main dashboard home page."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"page_title": "Dashboard"}
    )
