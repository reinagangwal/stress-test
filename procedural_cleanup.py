# procedural_cleanup.py
import psycopg2
import logging
from config import DB_CONFIG, TARGET_TABLE
from procedure_generator import get_all_tables, get_related_tables

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def call_delete_procedure(conn, table):
    proc_name = f'delete_dummy_{table}'
    with conn.cursor() as cur:
        cur.execute(f"CALL {proc_name}();")
        logging.info(f"✅ Called {proc_name}()")
        conn.commit()

def cleanup():
    if TARGET_TABLE:
        tables = get_related_tables(TARGET_TABLE)
        logging.info(f"🧹 Cleaning up only: {tables} (TARGET_TABLE={TARGET_TABLE})")
    else:
        tables = get_all_tables()
        logging.info(f"🧹 Cleaning up all tables.")
    logging.info(f"🧹 Starting cleanup of dummy data...")
    with psycopg2.connect(**DB_CONFIG) as conn:
        for table in tables:
            call_delete_procedure(conn, table)
    logging.info(f"✅ Cleanup completed.")

cleanup()
