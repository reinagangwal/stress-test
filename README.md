# stress-test

## Overview

**stress-test** is a toolkit for stress-testing PostgreSQL databases. It automates the generation of stored procedures for inserting and deleting dummy data, runs configurable stress tests by bulk-inserting data into your tables, and cleans up the test data afterward. The toolkit is useful for benchmarking, load testing, and validating the performance and integrity of your database schema under heavy write loads.

## Features
- **Automatic Procedure Generation:** Creates PostgreSQL procedures for inserting and deleting dummy data for each table.
- **No Strict Schema Requirements:** Works with databases that do not have standard primary key or foreign key relationships.
- **Constraint-Aware Dummy Data:** Automatically detects value constraints (such as enums or check constraints) for columns and generates dummy data that respects these constraints.
- **Configurable Stress Testing:** Bulk-inserts millions of rows into all tables or a specific table and its related tables.
- **System Metrics Logging:** Logs CPU and memory usage before and after each table's test.
- **Automated Cleanup:** Removes all dummy data after testing.
- **Flexible Configuration:** Easily control which steps to run and set batch sizes via `config.py`.

## Requirements
- Python 3.x
- PostgreSQL database
- Python packages: `psycopg2`, `psutil`, `inflect`

Install dependencies:
```bash
pip install psycopg2 psutil inflect
```

## Configuration
Edit `config.py` to set your database connection and test parameters:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'parkingdb',
    'user': 'postgres',
    'password': 'your_password'
}

TARGET_TABLE = None     # Set to a table name to test only that table and its relations, or None for all tables.
BATCH_SIZE = 1000000    # Number of rows to insert per table
RUN_PROCEDURE_GENERATOR = False  # Set True to (re)generate procedures
RUN_STRESS_TEST = False          # Set True to run stress test
RUN_CLEANUP = True               # Set True to clean up after test
```

## Usage
1. **Configure** your settings in `config.py`.
2. **Run the main script:**
   ```bash
   python config.py
   ```
   The script will execute the enabled steps in order:
   - Generate procedures (if `RUN_PROCEDURE_GENERATOR` is True)
   - Run the stress test (if `RUN_STRESS_TEST` is True)
   - Clean up test data (if `RUN_CLEANUP` is True)

## How It Works
- **Procedure Generation:**
  - Scans your database schema and creates `insert_dummy_<table>` and `delete_dummy_<table>` procedures for each table.
- **Stress Testing:**
  - Calls the insert procedures in bulk for each table, logging system metrics and timing.
- **Cleanup:**
  - Calls the delete procedures to remove all dummy data.

## Notes
- Ensure your database user has permission to create procedures and insert/delete data.
- The toolkit does **not** require your database to have standard primary key or foreign key relationships.
- For best results, start with a clean database or back up your data.

