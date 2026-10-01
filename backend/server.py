import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, db, ensure_indexes
from lib.debts import migrate_returned_debts
from lib.financial_operations import recover_financial_operations
from lib.financial_operations import financial_lock
from lib.runtime_lock import single_writer


# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    with single_writer(db.name):
        try:
            await prepare_database()
            yield
        finally:
            client.close()


async def prepare_database():
    await recover_financial_operations()
    await ensure_indexes()
    await migrate_returned_debts()
    for name in ('excel_events', 'import_batches', 'transactions', 'transaction_details'):
        try:
            await db[name].create_index('id', unique=True, name='id_unique')
        except Exception as exc:
            logging.getLogger(__name__).error("create id index on %s: %s", name, exc)
    try:
        await db.excel_parameters.create_index('month', unique=True, name='month_unique')
        await db.excel_snapshots.create_index([('source', 1), ('month', 1)], unique=True, name='source_month_unique')
    except Exception as exc:
        logging.getLogger(__name__).error("create excel indexes: %s", exc)


# Create the main app without a prefix
app = FastAPI(
    lifespan=lifespan,
    # Skema/dokumentasi API tidak diekspos di produksi (set ENABLE_API_DOCS=true untuk dev).
    docs_url="/docs" if os.environ.get("ENABLE_API_DOCS", "false").lower() == "true" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if os.environ.get("ENABLE_API_DOCS", "false").lower() == "true" else None,
)


@app.middleware("http")
async def consistent_financial_reads(request, call_next):
    # Wait until a write/rollback finishes so UI and reports never see its partial state.
    if request.method == "GET" and request.url.path.startswith("/api/"):
        async with financial_lock:
            return await call_next(request)
    return await call_next(request)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

# Mount resource routers (each exports its own APIRouter, all under /api)
from routers import (auth, customers, dashboard, expenses, laravel_bundle,
                     payables, products, receivables, reports, stock_in,
                     suppliers, transactions, vehicles)
from routers import excel_reports, imports as imports_router
from routers import books
from lib.dates import today_iso
from lib.auth import require_user
from fastapi import Depends


@api_router.get('/system', dependencies=[Depends(require_user)])
async def system_info():
    return {'today': today_iso(), 'timezone': os.environ['APP_TZ'], 'xp_supported': False,
            'offline_installer': False, 'source_commit': '2382f5bc3bbbaf3c230319701d8351c1f0e80881'}

api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(customers.router)
api_router.include_router(suppliers.router)
api_router.include_router(transactions.router)
api_router.include_router(receivables.router)
api_router.include_router(payables.router)
api_router.include_router(expenses.router)
api_router.include_router(dashboard.router)
api_router.include_router(stock_in.router)
api_router.include_router(vehicles.router)
api_router.include_router(reports.router)
api_router.include_router(laravel_bundle.router)
api_router.include_router(excel_reports.router)
api_router.include_router(imports_router.router)
api_router.include_router(books.router)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
