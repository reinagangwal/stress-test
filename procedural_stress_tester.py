# procedural_stress_tester.py
import psycopg2
import logging
import time
from config import DB_CONFIG, TARGET_TABLE
from config import BATCH_SIZE
from procedure_generator import get_all_tables, get_related_tables
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def log_system_metrics(prefix=""):
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    logging.info(f"{prefix}CPU: {cpu}%, Memory: {mem.percent}% used ({mem.used // (1024*1024)}MB/{mem.total // (1024*1024)}MB)")

def _format_proc_name(prefix, table_ref):
    if isinstance(table_ref, tuple):
        schema, table = table_ref
        return f"{prefix}_{schema}_{table}"
    return f"{prefix}_{table_ref}"

def call_insert_procedure(conn, table, n):
    proc_name = _format_proc_name('insert_dummy', table)
    start_time = time.time()
    try:
        with conn.cursor() as cur:
            cur.execute(f"CALL {proc_name}(%s);", (n,))
            conn.commit()
        elapsed = round(time.time() - start_time, 2)
        logging.info(f"✅ Called {proc_name}({n}) in {elapsed}s")
    except Exception as e:
        logging.error(f"❌ Error calling {proc_name}({n}): {e}")
        raise

def stress_test(batch_size):
    if TARGET_TABLE:
        tables = get_related_tables(TARGET_TABLE)
        logging.info(f"🔬 Stress testing only: {tables} (TARGET_TABLE={TARGET_TABLE})")
    else:
        tables = get_all_tables()
        logging.info(f"🚀 Stress testing all tables.")
    start = time.time()
    logging.info(f"🚀 Starting stress test with batch size: {batch_size}")
    with psycopg2.connect(**DB_CONFIG) as conn:
        for table in tables:
            log_system_metrics(prefix=f"[Before {table}] ")
            call_insert_procedure(conn, table, batch_size)
            log_system_metrics(prefix=f"[After {table}]  ")
    end = time.time()
    elapsed = round(end - start, 2)
    logging.info(f"✅ Completed batch of {batch_size} rows. Inserted in {elapsed} seconds.")

def call_delete_procedure(conn, table):
    proc_name = _format_proc_name('delete_dummy', table)
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

if __name__ == "__main__":
    stress_test(BATCH_SIZE)
    


