import psycopg2
from config import DB_CONFIG, SCHEMAS_TO_SCAN
import re
import datetime

type_map = {
    'integer': '1',
    'bigint': '1',
    'smallint': '1',
    'character varying': "'DummyText'",
    'varchar': "'DummyText'",
    'text': "'DummyText'",
    'date': 'CURRENT_DATE',
    'timestamp without time zone': 'CURRENT_TIMESTAMP',
    'timestamp with time zone': 'CURRENT_TIMESTAMP',
    'time without time zone': 'CURRENT_TIME',
    'boolean': 'TRUE',
    'numeric': '1.23',
    'decimal': '1.23',
    'real': '1.23',
    'double precision': '1.23',
}

def get_all_tables():
    all_tables = []
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            for schema in SCHEMAS_TO_SCAN:
                try:
                    cur.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_type = 'BASE TABLE';
                    """, (schema,))
                    tables = cur.fetchall()
                    for table in tables:
                        all_tables.append((schema, table[0]))
                    print(f"[INFO] Found {len(tables)} tables in schema '{schema}'")
                except Exception as e:
                    print(f"[WARN] Could not scan schema '{schema}': {e}")
                    continue
    return all_tables

def get_related_tables(target_schema, target_table):
    from inflect import engine as inflect_engine
    inflect = inflect_engine()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            related_tables = {(target_schema, target_table)}
            queue = [(target_schema, target_table)]
            # Add logical relation: tables with <target_table_singular>_id column
            singular = inflect.singular_noun(target_table) or target_table.rstrip('s')
            logical_column = f"{singular}_id"
            
            # Search across all schemas for related tables
            for schema in SCHEMAS_TO_SCAN:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.columns
                    WHERE column_name = %s AND table_schema = %s;
                """, (logical_column, schema))
                for row in cur.fetchall():
                    table = row[0]
                    if (schema, table) not in related_tables:
                        related_tables.add((schema, table))
                        queue.append((schema, table))
            while queue:
                current_schema, current_table = queue.pop(0)
                # Find tables that the current_table references (parent tables)
                cur.execute("""
                    SELECT ccu.table_schema, ccu.table_name
                    FROM information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s AND tc.table_schema = %s;
                """, (current_table,))
                for row in cur.fetchall():
                    table = row[0]
                    if table not in related_tables:
                        related_tables.add(table)
                        queue.append(table)
                # Find tables that reference the current_table (child tables)
                cur.execute("""
                    SELECT cl.relname AS table_name
                    FROM pg_constraint AS con
                    JOIN pg_class AS cl ON con.conrelid = cl.oid
                    JOIN pg_namespace AS nsp ON cl.relnamespace = nsp.oid
                    JOIN pg_class AS refcl ON con.confrelid = refcl.oid
                    WHERE con.contype = 'f' AND refcl.relname = %s AND nsp.nspname = 'public';
                """, (current_table,))
                for row in cur.fetchall():
                    table = row[0]
                    if table not in related_tables:
                        related_tables.add(table)
                        queue.append(table)
            return list(related_tables)

def get_columns_for_table(schema, table):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """, (schema, table))
            return cur.fetchall()

def has_id_column(columns):
    return any(col == 'id' for col, _ in columns)

def get_allowed_values_for_column(table, column):
    """
    Returns a list of allowed values for a column if it is an enum or has a check constraint, otherwise None.
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Check for enum type
            cur.execute('''
                SELECT t.typname
                FROM pg_catalog.pg_type t
                JOIN pg_catalog.pg_attribute a ON a.atttypid = t.oid
                JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
                WHERE c.relname = %s AND a.attname = %s AND t.typtype = 'e';
            ''', (table, column))
            enum_type = cur.fetchone()
            if enum_type:
                cur.execute('''
                    SELECT enumlabel FROM pg_enum WHERE enumtypid = (
                        SELECT oid FROM pg_type WHERE typname = %s
                    ) ORDER BY enumsortorder;
                ''', (enum_type[0],))
                return [row[0] for row in cur.fetchall()]

            # Check for check constraint
            cur.execute('''
                SELECT pg_get_constraintdef(con.oid)
                FROM pg_constraint con
                INNER JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE rel.relname = %s AND con.contype = 'c';
            ''', (table,))
            for (constraint_def,) in cur.fetchall():
                if f'({column} = ' in constraint_def or f'{column} IN (' in constraint_def:
                    # Try to extract allowed values from the constraint definition
                    match = re.search(rf"{column} IN \(([^)]+)\)", constraint_def)
                    if match:
                        values = [v.strip().strip("'") for v in match.group(1).split(',')]
                        return values
            return None

def get_most_common_values_for_column(schema, table, column, limit=5):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT {column}, COUNT(*) as freq
                FROM {schema}.{table}
                WHERE {column} IS NOT NULL
                GROUP BY {column}
                ORDER BY freq DESC
                LIMIT %s;
            """, (limit,))
            return [row[0] for row in cur.fetchall()]

# Update generate_insert_procedure to use most common values

def generate_insert_procedure(schema, table, columns):
    # Always skip 'id' column for inserts so PostgreSQL handles it
    col_names = [col for col, _ in columns if col != 'id']
    col_types = [typ for col, typ in columns if col != 'id']
    
    # Ensure we have exactly the same number of values as columns
    if len(col_names) != len(col_types):
        raise ValueError(f"Column count mismatch in {table}: {len(col_names)} names vs {len(col_types)} types")
    
    values = []
    for idx, (col, typ) in enumerate(zip(col_names, col_types)):
        # Try to get most common values for this column
        common_values = get_most_common_values_for_column(schema, table, col, limit=5)
        if 1 <= len(common_values) <= 5:
            # Use CASE statement to cycle through values, referencing gs.row_number
            if len(common_values) == 1:
                # For single value, just use the value directly
                val = common_values[0]
                if isinstance(val, datetime.datetime):
                    case_stmt = f"TIMESTAMP '{val}'"
                elif isinstance(val, datetime.date):
                    case_stmt = f"DATE '{val}'"
                elif isinstance(val, (bytes, memoryview)):
                    case_stmt = "NULL"
                elif isinstance(val, (list, tuple)):
                    case_stmt = "NULL"
                elif isinstance(val, str):
                    case_stmt = f"'{val}'"
                elif isinstance(val, (int, float)):
                    case_stmt = str(val)
                elif hasattr(val, '__float__'):  # Handle Decimal types
                    try:
                        case_stmt = str(float(val))
                    except (ValueError, TypeError):
                        case_stmt = "NULL"
                elif isinstance(val, dict):
                    case_stmt = "NULL"
                else:
                    print(f"[WARN] Unhandled type for column {col}: {type(val)} value={val!r}")
                    case_stmt = "NULL"
            else:
                # For multiple values, use CASE statement
                case_stmt = "CASE (gs.row_number % {n})".format(n=len(common_values))
                for i, v in enumerate(common_values):
                    if isinstance(v, datetime.datetime):
                        val = f"TIMESTAMP '{v}'"
                    elif isinstance(v, datetime.date):
                        val = f"DATE '{v}'"
                    elif isinstance(v, (bytes, memoryview)):
                        val = "NULL"
                    elif isinstance(v, (list, tuple)):
                        val = "NULL"
                    elif isinstance(v, str):
                        val = f"'{v}'"
                    elif isinstance(v, (int, float)):
                        val = str(v)
                    elif hasattr(v, '__float__'):  # Handle Decimal types
                        try:
                            val = str(float(v))
                        except (ValueError, TypeError):
                            val = "NULL"
                    elif isinstance(v, dict):
                        val = "NULL"
                    else:
                        print(f"[WARN] Unhandled type for column {col}: {type(v)} value={val!r}")
                        val = "NULL"
                    case_stmt += f" WHEN {i} THEN {val}"
                case_stmt += " END"
            values.append(case_stmt)
        elif col.endswith('_id'):
            values.append('1')
        else:
            values.append(type_map.get(typ, 'NULL'))
    
    # Final validation: ensure we have exactly one value per column
    if len(values) != len(col_names):
        raise ValueError(f"Column/value count mismatch for table {table}: {len(col_names)} vs {len(values)}")
    
    # Debug logging to help identify any issues
    print(f"[DEBUG] Table {table}: {len(col_names)} columns, {len(values)} values")
    print(f"[DEBUG] Columns: {col_names}")
    print(f"[DEBUG] Values: {[str(v)[:50] + '...' if len(str(v)) > 50 else str(v) for v in values]}")
    
    select_list = ', '.join(values)
    insert_cols = ', '.join(col_names)
    
    proc = f"""
CREATE OR REPLACE PROCEDURE insert_dummy_{schema}_{table}(n integer)
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO {schema}.{table} ({insert_cols})
  SELECT {select_list}
  FROM (
    SELECT *, row_number() OVER () as row_number FROM generate_series(1, n)
  ) gs;
END;
$$;
"""
    return proc

def generate_delete_procedure(schema, table, columns):
    text_cols = [col for col, typ in columns if typ in ('character varying', 'varchar', 'text') and col != 'id']
    has_id = has_id_column(columns)
    if text_cols:
        col = text_cols[0]
        where = f"WHERE {col} LIKE 'Dummy%'"
    else:
        where = ''
    reset_seq = ''
    if has_id:
        reset_seq = f"PERFORM setval(pg_get_serial_sequence('{schema}.{table}', 'id'), COALESCE((SELECT MAX(id) FROM {schema}.{table}), 1), false);"
    proc = f"""
CREATE OR REPLACE PROCEDURE delete_dummy_{schema}_{table}()
LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM {schema}.{table} {where};
  {reset_seq}
END;
$$;
"""
    return proc

def main():
    tables = get_all_tables()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            for schema, table in tables:
                try:
                    print(f'Processing table {schema}.{table}...')
                    columns = get_columns_for_table(schema, table)
                    insert_proc = generate_insert_procedure(schema, table, columns)
                    delete_proc = generate_delete_procedure(schema, table, columns)
                    print(f'Installing procedures for {schema}.{table}...')
                    cur.execute(insert_proc)
                    cur.execute(delete_proc)
                except Exception as e:
                    print(f'Error installing procedures for {schema}.{table}: {e}')
                    print(f'Insert procedure SQL: {insert_proc}')
                    print(f'Delete procedure SQL: {delete_proc}')
                    raise
            conn.commit()
    print('All procedures installed.')

if __name__ == '__main__':
    main() 