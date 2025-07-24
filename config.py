# config.py

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'parkingdb',  
    'user': 'postgres',
    'password': 'reina123'
}

# User requirements:

TARGET_TABLE = None     # Set to a specific table name to test only that table and its relations. # Set to None to test all tables.
BATCH_SIZE = 1000000     # Number of rows to insert per table
RUN_PROCEDURE_GENERATOR = False  # Set True to (re)generate procedures
RUN_STRESS_TEST = False         # Set True to run stress test
RUN_CLEANUP = True            # Set True to clean up after test























if __name__ == "__main__":
    import sys
    import os
    import importlib.util
    import subprocess
    
    def run_script(path):
        spec = importlib.util.spec_from_file_location("mod", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load script: {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    base = os.path.dirname(os.path.abspath(__file__))
    procgen = os.path.join(base, "procedure_generator.py")
    stress = os.path.join(base, "procedural_stress_tester.py")
    cleanup = os.path.join(base, "procedural_cleanup.py")

    if RUN_PROCEDURE_GENERATOR:
        print("[CONFIG] Running procedure generator...")
        subprocess.run([sys.executable, procgen], check=True)
    if RUN_STRESS_TEST:
        print("[CONFIG] Running stress tester...")
        subprocess.run([sys.executable, stress], check=True)
    if RUN_CLEANUP:
        print("[CONFIG] Running cleanup...")
        subprocess.run([sys.executable, cleanup], check=True)
    print("[CONFIG] Done.")
