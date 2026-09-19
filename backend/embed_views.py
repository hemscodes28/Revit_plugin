import os

import psycopg

from embedding_service import create_embedding


DATABASE_URL = (
    "host=127.0.0.1 "
    "port=5432 "
    "dbname=revitai "
    "user=postgres "
    f"password={os.environ['REVITAI_DB_PASSWORD']}"
)


def main():

    print("Connecting to PostgreSQL...")

    with psycopg.connect(DATABASE_URL) as connection:

        print("Connected to PostgreSQL.")

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    view_type,
                    level_name,
                    description
                FROM revit_views
                ORDER BY id;
                """
            )

            rows = cursor.fetchall()

            print(f"Found {len(rows)} views.")

            for index, row in enumerate(rows, start=1):

                view_id = row[0]
                name = row[1]
                view_type = row[2]
                level_name = row[3]
                description = row[4]

                level_text = (
                    level_name
                    if level_name is not None
                    else "Not associated with a level"
                )

                description_text = (
                    description
                    if description is not None
                    else "No description available"
                )

                text = (
                    f"View name: {name}. "
                    f"View type: {view_type}. "
                    f"Level: {level_text}. "
                    f"Description: {description_text}."
                )

                print(
                    f"[{index}/{len(rows)}] "
                    f"Creating embedding for: {name}"
                )

                embedding = create_embedding(text)

                cursor.execute(
                    """
                    UPDATE revit_views
                    SET embedding = %s
                    WHERE id = %s;
                    """,
                    (
                        embedding,
                        view_id
                    )
                )

            connection.commit()

            print()
            print("========================================")
            print("Embedding generation completed.")
            print(f"Views processed: {len(rows)}")
            print("========================================")


if __name__ == "__main__":
    main()