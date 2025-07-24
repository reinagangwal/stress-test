import psycopg2
from config import DB_CONFIG
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
    'real': '1.23',
    'double precision': '1.23',
}

def get_all_tables():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
            """)
            return [row[0] for row in cur.fetchall()]

def get_related_tables(target_table):
    from inflect import engine as inflect_engine
    inflect = inflect_engine()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            related_tables = {target_table}
            queue = [target_table]
            # Add logical relation: tables with <target_table_singular>_id column
            singular = inflect.singular_noun(target_table) or target_table.rstrip('s')
            logical_column = f"{singular}_id"
            cur.execute("""
                SELECT table_name
                FROM information_schema.columns
                WHERE column_name = %s AND table_schema = 'public';
            """, (logical_column,))
            for row in cur.fetchall():
                table = row[0]
                if table not in related_tables:
                    related_tables.add(table)
                    queue.append(table)
            while queue:
                current_table = queue.pop(0)
                # Find tables that the current_table references (parent tables)
                cur.execute("""
                    SELECT ccu.table_name
                    FROM information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s;
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

def get_columns_for_table(table):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, (table,))
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

def get_most_common_values_for_column(table, column, limit=5):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT {column}, COUNT(*) as freq
                FROM {table}
                WHERE {column} IS NOT NULL
                GROUP BY {column}
                ORDER BY freq DESC
                LIMIT %s;
            """, (limit,))
            return [row[0] for row in cur.fetchall()]

# Update generate_insert_procedure to use most common values

def generate_insert_procedure(table, columns):
    # Always skip 'id' column for inserts so PostgreSQL handles it
    col_names = [col for col, _ in columns if col != 'id']
    col_types = [typ for col, typ in columns if col != 'id']
    values = []
    for idx, (col, typ) in enumerate(zip(col_names, col_types)):
        # Try to get most common values for this column
        common_values = get_most_common_values_for_column(table, col, limit=5)
        if 1 <= len(common_values) <= 5:
            # Use CASE statement to cycle through values, referencing gs.row_number
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
                elif isinstance(v, dict):
                    val = "NULL"
                else:
                    print(f"[WARN] Unhandled type for column {col}: {type(v)} value={v!r}")
                    val = "NULL"
                case_stmt += f" WHEN {i} THEN {val}"
            case_stmt += " END"
            values.append(case_stmt)
        elif col.endswith('_id'):
            values.append('1')
        else:
            values.append(type_map.get(typ, 'NULL'))
    select_list = ', '.join(values)
    insert_cols = ', '.join(col_names)
    proc = f"""
CREATE OR REPLACE PROCEDURE insert_dummy_{table}(n integer)
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO {table} ({insert_cols})
  SELECT {select_list}
  FROM (
    SELECT *, row_number() OVER () as row_number FROM generate_series(1, n)
  ) gs;
END;
$$;
"""
    return proc

def generate_delete_procedure(table, columns):
    text_cols = [col for col, typ in columns if typ in ('character varying', 'varchar', 'text') and col != 'id']
    has_id = has_id_column(columns)
    if text_cols:
        col = text_cols[0]
        where = f"WHERE {col} LIKE 'Dummy%'"
    else:
        where = ''
    reset_seq = ''
    if has_id:
        reset_seq = f"PERFORM setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), false);"
    proc = f"""
CREATE OR REPLACE PROCEDURE delete_dummy_{table}()
LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM {table} {where};
  {reset_seq}
END;
$$;
"""
    return proc

def main():
    tables = get_all_tables()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            for table in tables:
                columns = get_columns_for_table(table)
                insert_proc = generate_insert_procedure(table, columns)
                delete_proc = generate_delete_procedure(table, columns)
                print(f'Installing procedures for {table}...')
                cur.execute(insert_proc)
                cur.execute(delete_proc)
            conn.commit()
    print('All procedures installed.')

if __name__ == '__main__':
    main() 