import sqlite3
from pathlib import Path
from typing import Optional

# Path to the SQLite database file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "pharmacy.db"


def get_db_path(custom_path: Optional[Path | str] = None) -> Path:
    """Resolve and ensure parent directory for the database path."""
    if custom_path is not None:
        path = Path(custom_path)
    else:
        path = DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_db_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Create and return a SQLite connection with Row factory and foreign keys enabled."""
    resolved_path = get_db_path(db_path)
    conn = sqlite3.connect(str(resolved_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path | str] = None) -> None:
    """Initialize SQLite database tables for Phase 1 Foundation."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. inventory table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        med_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        current_stock INTEGER NOT NULL,
        reorder_point INTEGER NOT NULL,
        daily_sales INTEGER NOT NULL,
        lead_time_days INTEGER NOT NULL,
        expiry_date TEXT NOT NULL
    );
    """)

    # 2. vendors table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendors (
        vendor_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    );
    """)

    # 3. vendor_offers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendor_offers (
        vendor_id INTEGER NOT NULL,
        med_id INTEGER NOT NULL,
        base_price REAL NOT NULL,
        min_qty INTEGER NOT NULL,
        delivery_days INTEGER NOT NULL,
        PRIMARY KEY (vendor_id, med_id),
        FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id) ON DELETE CASCADE,
        FOREIGN KEY (med_id) REFERENCES inventory (med_id) ON DELETE CASCADE
    );
    """)

    # 4. purchase_orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        po_id INTEGER PRIMARY KEY AUTOINCREMENT,
        med_id INTEGER NOT NULL,
        vendor_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_cost REAL NOT NULL,
        delivery_days INTEGER NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY (med_id) REFERENCES inventory (med_id) ON DELETE RESTRICT,
        FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id) ON DELETE RESTRICT
    );
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database tables initialized successfully.")
