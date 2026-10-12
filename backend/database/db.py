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
    """Initialize SQLite database tables for realistic ERP procurement."""
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

    # 2. vendors table (with reliability, email, payment terms)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendors (
        vendor_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        reliability REAL DEFAULT 0.95,
        contact_email TEXT,
        payment_terms TEXT DEFAULT 'Net 30'
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

    # 4. purchase_orders table (with safe lifecycle tracking)
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
        created_at TEXT,
        updated_at TEXT,
        received_quantity INTEGER DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (med_id) REFERENCES inventory (med_id) ON DELETE RESTRICT,
        FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id) ON DELETE RESTRICT
    );
    """)

    # 5. goods_receipts table (receiving verification and discrepancy tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goods_receipts (
        receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        med_id INTEGER NOT NULL,
        vendor_id INTEGER NOT NULL,
        received_qty INTEGER NOT NULL,
        batch_number TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        discrepancy_qty INTEGER DEFAULT 0,
        notes TEXT,
        received_at TEXT NOT NULL,
        FOREIGN KEY (po_id) REFERENCES purchase_orders (po_id) ON DELETE RESTRICT,
        FOREIGN KEY (med_id) REFERENCES inventory (med_id) ON DELETE RESTRICT,
        FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id) ON DELETE RESTRICT
    );
    """)

    # 6. inventory_batches table (batch-level expiry tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_batches (
        batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        med_id INTEGER NOT NULL,
        batch_number TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        expiry_date TEXT NOT NULL,
        received_at TEXT NOT NULL,
        FOREIGN KEY (med_id) REFERENCES inventory (med_id) ON DELETE CASCADE
    );
    """)

    # 7. audit_log table (decision, approval, order, and receipt audit trails)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Column migrations for existing tables if already created
    # Ensure vendors has reliability, contact_email, payment_terms
    v_cols = [r["name"] for r in cursor.execute("PRAGMA table_info(vendors)").fetchall()]
    if "reliability" not in v_cols:
        cursor.execute("ALTER TABLE vendors ADD COLUMN reliability REAL DEFAULT 0.95;")
    if "contact_email" not in v_cols:
        cursor.execute("ALTER TABLE vendors ADD COLUMN contact_email TEXT;")
    if "payment_terms" not in v_cols:
        cursor.execute("ALTER TABLE vendors ADD COLUMN payment_terms TEXT DEFAULT 'Net 30';")

    # Ensure purchase_orders has lifecycle columns
    po_cols = [r["name"] for r in cursor.execute("PRAGMA table_info(purchase_orders)").fetchall()]
    if "created_at" not in po_cols:
        cursor.execute("ALTER TABLE purchase_orders ADD COLUMN created_at TEXT;")
    if "updated_at" not in po_cols:
        cursor.execute("ALTER TABLE purchase_orders ADD COLUMN updated_at TEXT;")
    if "received_quantity" not in po_cols:
        cursor.execute("ALTER TABLE purchase_orders ADD COLUMN received_quantity INTEGER DEFAULT 0;")
    if "notes" not in po_cols:
        cursor.execute("ALTER TABLE purchase_orders ADD COLUMN notes TEXT;")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database tables initialized successfully with lifecycle & audit support.")
