"""
Used by the migrations that switch primary keys from sequential integers to
random UUIDs (accounts 0016, test_app 0040).

Existing rows get a new random id, and every foreign key that points to the
table is converted and filled in with the new ids. The foreign keys are looked
up in the database itself, so tables that are not part of the migration
history (e.g. leftovers from older versions of the app) are converted too.
"""


def convert_pk_to_uuid(cursor, table):
    # Earlier statements in the same transaction must not leave pending
    # foreign key checks, or the ALTER TABLEs below fail.
    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    cursor.execute(
        """
        SELECT c.conrelid::regclass::text, a.attname, c.conname,
               pg_get_constraintdef(c.oid), a.attnotnull
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
        WHERE c.contype = 'f' AND c.confrelid = %s::regclass
        """,
        [table],
    )
    foreign_keys = cursor.fetchall()

    cursor.execute(
        f'ALTER TABLE "{table}" ADD COLUMN "new_id" uuid NOT NULL DEFAULT gen_random_uuid()'
    )

    recreate = []
    for child, column, fk_name, fk_definition, not_null in foreign_keys:
        # Unique constraints and indexes on the column are dropped together
        # with it, so they are saved and recreated afterwards.
        cursor.execute(
            """
            SELECT 'ALTER TABLE ' || conrelid::regclass::text || ' ADD CONSTRAINT '
                   || quote_ident(conname) || ' ' || pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = %s::regclass AND contype = 'u'
              AND (SELECT attnum FROM pg_attribute WHERE attrelid = %s::regclass AND attname = %s) = ANY(conkey)
            """,
            [child, child, column],
        )
        recreate += [row[0] for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT pg_get_indexdef(i.indexrelid)
            FROM pg_index i
            WHERE i.indrelid = %s::regclass
              AND (SELECT attnum FROM pg_attribute WHERE attrelid = %s::regclass AND attname = %s) = ANY(i.indkey)
              AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conindid = i.indexrelid)
            """,
            [child, child, column],
        )
        recreate += [row[0] for row in cursor.fetchall()]

        cursor.execute(f'ALTER TABLE {child} DROP CONSTRAINT "{fk_name}"')
        cursor.execute(f'ALTER TABLE {child} ADD COLUMN "{column}__uuid" uuid')
        cursor.execute(
            f'UPDATE {child} SET "{column}__uuid" = parent."new_id" '
            f'FROM "{table}" parent WHERE {child}."{column}" = parent."id"'
        )
        cursor.execute(f'ALTER TABLE {child} DROP COLUMN "{column}"')
        cursor.execute(f'ALTER TABLE {child} RENAME COLUMN "{column}__uuid" TO "{column}"')
        if not_null:
            cursor.execute(f'ALTER TABLE {child} ALTER COLUMN "{column}" SET NOT NULL')

        recreate.append(f'ALTER TABLE {child} ADD CONSTRAINT "{fk_name}" {fk_definition}')

    # Swap the primary key over to the new column
    cursor.execute(f'ALTER TABLE "{table}" DROP COLUMN "id"')
    cursor.execute(f'ALTER TABLE "{table}" RENAME COLUMN "new_id" TO "id"')
    cursor.execute(f'ALTER TABLE "{table}" ALTER COLUMN "id" DROP DEFAULT')
    cursor.execute(f'ALTER TABLE "{table}" ADD CONSTRAINT "{table}_pkey" PRIMARY KEY ("id")')

    # Foreign keys last, now that the primary key they reference exists again
    for statement in sorted(recreate, key=lambda s: "FOREIGN KEY" in s):
        cursor.execute(statement)


def converter(*tables):
    """A RunPython function that converts the given tables."""
    def run(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            for table in tables:
                convert_pk_to_uuid(cursor, table)
    return run
