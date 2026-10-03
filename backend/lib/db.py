"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.write_concern import WriteConcern

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client.get_database(os.environ["DB_NAME"], write_concern=WriteConcern(w=1, j=True))

logger = logging.getLogger(__name__)

# One entry per collection: every field a route filters, sorts, or dedupes on. Applied by ensure_indexes() at startup.
INDEXES: dict[str, list[IndexModel]] = {
    "checkout_requests": [IndexModel([("id", ASCENDING)], name="id_unique", unique=True)],
    "status_checks": [IndexModel([("timestamp", DESCENDING)], name="timestamp_desc")],
    "users": [IndexModel([("username", ASCENDING)], name="username_unique", unique=True)],
    "sessions": [
        IndexModel([("token", ASCENDING)], name="token_unique", unique=True),
        IndexModel([("expires_at", ASCENDING)], name="expires_at_ttl", expireAfterSeconds=0),
    ],
    "products": [
        IndexModel([("id", ASCENDING)], name="id_unique", unique=True),
        IndexModel([("type", ASCENDING), ("name", ASCENDING)], name="type_name"),
    ],
    "customers": [IndexModel([("id", ASCENDING)], name="id_unique", unique=True)],
    "suppliers": [IndexModel([("id", ASCENDING)], name="id_unique", unique=True)],
    "transactions": [
        IndexModel([("id", ASCENDING)], name="id_unique", unique=True),
        IndexModel([("invoice_number", ASCENDING)], name="invoice_unique", unique=True),
        IndexModel([("date_key", ASCENDING), ("date", DESCENDING)], name="date_key_date_desc"),
        IndexModel([("status", ASCENDING)], name="status"),
        IndexModel([("vehicle_plate", ASCENDING), ("date", DESCENDING)], name="plate_date_desc"),
    ],
    "stock_in": [
        IndexModel([("id", ASCENDING)], name="id_unique", unique=True),
        IndexModel([("reference", ASCENDING)], name="reference_unique", unique=True),
        IndexModel([("date_key", ASCENDING), ("date", DESCENDING)], name="date_key_date_desc"),
    ],
    "transaction_details": [
        IndexModel([("transaction_id", ASCENDING)], name="transaction_id"),
        IndexModel([("product_id", ASCENDING)], name="product_id"),
    ],
    "accounts_receivable": [
        IndexModel([("id", ASCENDING)], name="id_unique", unique=True),
        IndexModel([("status", ASCENDING), ("due_date", ASCENDING)], name="status_due"),
    ],
    "accounts_payable": [
        IndexModel([("id", ASCENDING)], name="id_unique", unique=True),
        IndexModel([("status", ASCENDING), ("due_date", ASCENDING)], name="status_due"),
    ],
    "expenses": [
        IndexModel([("id", ASCENDING)], name="id_unique", unique=True),
        IndexModel([("date", DESCENDING)], name="date_desc"),
    ],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:  # never block boot on an index; the log line names what to fix
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)
