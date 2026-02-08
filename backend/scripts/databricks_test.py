from __future__ import annotations

from app.databricks_client import query


def main() -> None:
    rows = query("SELECT * from range(10)")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
