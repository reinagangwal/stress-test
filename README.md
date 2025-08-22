# stress-test

## Overview

**stress-test** is a comprehensive toolkit for stress-testing both PostgreSQL databases and REST APIs. It automates the generation of stored procedures for inserting and deleting dummy data, runs configurable stress tests by bulk-inserting data into your tables, and performs API load testing with concurrent requests. The toolkit is useful for benchmarking, load testing, and validating the performance and integrity of your database schema and API endpoints under heavy loads.

## Features
- **Automatic Procedure Generation:** Creates PostgreSQL procedures for inserting and deleting dummy data for each table.
- **No Strict Schema Requirements:** Works with databases that do not have standard primary key or foreign key relationships.
- **Constraint-Aware Dummy Data:** Automatically detects value constraints (such as enums or check constraints) for columns and generates dummy data that respects these constraints.
- **Configurable Stress Testing:** Bulk-inserts millions of rows into all tables or a specific table and its related tables.
- **System Metrics Logging:** Logs CPU and memory usage before and after each table's test.
- **Automated Cleanup:** Removes all dummy data after testing.
- **Flexible Configuration:** Easily control which steps to run and set batch sizes via `config.py`.
- **General-Purpose API Load Testing:** Performs concurrent API requests with configurable load parameters - works with any REST API.
- **Multiple Authentication Support:** Supports Bearer tokens, API keys, and Basic authentication.
- **Success Criteria Validation:** Validates response times, success rates, and error rates against configurable thresholds.
- **Generic Dummy Data Generation:** Creates realistic test data for API requests without hardcoded dependencies on specific APIs.
- **Universal Cleanup:** Automatically identifies and cleans up test data using common patterns, works with any API structure.

## Requirements
- Python 3.x
- PostgreSQL database (for database testing)
- Python packages: `psycopg2`, `psutil`, `inflect`, `requests`

Install dependencies:
```bash
pip install psycopg2 psutil inflect requests
```

## Configuration
Edit `config.py` to set your database connection and test parameters:

```python
# Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'parkingdb',
    'user': 'postgres',
    'password': 'your_password'
}

# Database Testing Control
TARGET_TABLE = None     # Set to a table name to test only that table and its relations, or None for all tables.
BATCH_SIZE = 1000000    # Number of rows to insert per table
RUN_PROCEDURE_GENERATOR = False  # Set True to (re)generate procedures
RUN_STRESS_TEST = False          # Set True to run stress test
RUN_CLEANUP = True               # Set True to clean up after test

# API Testing Configuration
API_CONFIG = {
    'base_url': 'https://api.example.com',
    'auth_type': 'bearer',  # 'bearer', 'api_key', 'basic', 'none'
    'auth_token': 'your_token_here',
    'api_key': 'your_api_key_here',
    'username': 'your_username',
    'password': 'your_password',
    'concurrent_users': 50,
    'requests_per_second': 100,
    'test_duration_minutes': 10,
    'endpoints': [
        {'method': 'GET', 'path': '/users', 'expected_status': 200},
        {'method': 'POST', 'path': '/users', 'expected_status': 201},
        {'method': 'GET', 'path': '/products', 'expected_status': 200},
        {'method': 'POST', 'path': '/products', 'expected_status': 201},
        # Add more endpoints as needed
    ]
}

# API Testing Success Criteria
API_SUCCESS_CRITERIA = {
    'response_time_ms': 2000,  # 2 seconds max
    'success_rate_percent': 99,  # 99% success rate
    'max_error_rate_percent': 1   # 1% max error rate
}

# API Testing Control Flags
RUN_API_STRESS_TEST = False      # Set True to run API stress test
RUN_API_CLEANUP = False          # Set True to clean up API test data (if applicable)
```

## Usage
1. **Configure** your settings in `config.py`.
2. **Run the main script:**
   ```bash
   python config.py
   ```
   The script will execute the enabled steps in order:
   - Generate procedures (if `RUN_PROCEDURE_GENERATOR` is True)
   - Run the database stress test (if `RUN_STRESS_TEST` is True)
   - Clean up database test data (if `RUN_CLEANUP` is True)
   - Run the API stress test (if `RUN_API_STRESS_TEST` is True)
   - Clean up API test data (if `RUN_API_CLEANUP` is True)

## How It Works
- **Database Testing:**
  - Scans your database schema and creates `insert_dummy_<table>` and `delete_dummy_<table>` procedures for each table.
  - Calls the insert procedures in bulk for each table, logging system metrics and timing.
  - Calls the delete procedures to remove all dummy data.
- **API Testing:**
  - Makes concurrent HTTP requests to configured endpoints.
  - Generates realistic dummy data for POST/PUT requests based on endpoint patterns.
  - Validates response times, status codes, and success rates against configurable thresholds.
  - Supports multiple authentication methods (Bearer token, API key, Basic auth).
  - Cleans up test data created during API testing.

## Notes
- Ensure your database user has permission to create procedures and insert/delete data.
- The toolkit does **not** require your database to have standard primary key or foreign key relationships.
- For API testing, ensure your API endpoints are accessible and properly configured.
- The API cleanup feature requires your API to support DELETE operations for test data removal.
- For best results, start with a clean database or back up your data.

## License
MIT

