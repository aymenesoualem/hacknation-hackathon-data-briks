from __future__ import annotations

from databricks import sql

from app.config import settings


def get_connection():
    if not settings.databricks_server_hostname:
        raise RuntimeError("DATABRICKS_SERVER_HOSTNAME is not set")
    if not settings.databricks_http_path:
        raise RuntimeError("DATABRICKS_HTTP_PATH is not set")
    if not settings.databricks_access_token:
        raise RuntimeError("DATABRICKS_ACCESS_TOKEN is not set")

    return sql.connect(
        server_hostname=settings.databricks_server_hostname,
        http_path=settings.databricks_http_path,
        access_token=settings.databricks_access_token,
    )


def query(sql_text: str):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(sql_text)
        return cursor.fetchall()
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        connection.close()
