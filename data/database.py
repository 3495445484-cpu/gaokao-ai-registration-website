import json
import sqlite3
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "app.db"


TABLE_CONFIG = {
    "majors": {
        "file": "majors.json",
        "json_fields": {"tags", "risk_factors"},
    },
    "schools": {
        "file": "schools.json",
        "json_fields": {"tags"},
    },
    "quotes": {
        "file": "quotes.json",
        "json_fields": {"topics"},
    },
    "school_admissions_urls": {
        "file": "school_admissions_urls.json",
        "json_fields": {"payload"},
    },
}

INT_FIELDS = {
    "salary_median_5yr",
    "salary_entry",
    "irreplaceability",
    "average_salary",
    "count",
    "duplicate_count",
}
FLOAT_FIELDS = {"employment_rate"}
BOOL_FIELDS = {"requires_grad_school", "is_classic"}


def load_json(filename: str) -> list[dict[str, Any]] | dict[str, Any]:
    with (DATA_DIR / filename).open("r", encoding="utf-8") as f:
        return json.load(f)


def _columns_for(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def _encode_value(value: Any, force_json: bool = False) -> Any:
    if force_json or isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return int(value)
    return value


def _decode_value(value: Any, force_json: bool = False) -> Any:
    if value is None:
        return None
    if force_json and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [] if value == "" else value
    return value


def _restore_scalar_type(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in BOOL_FIELDS:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "是"}
        return bool(value)
    if key in INT_FIELDS:
        return int(value)
    if key in FLOAT_FIELDS:
        return float(value)
    return value


def initialize_database(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        for table, config in TABLE_CONFIG.items():
            source_data = load_json(config["file"])
            if table == "school_admissions_urls" and isinstance(source_data, dict):
                conn.execute(f"DROP TABLE IF EXISTS {table}")
                conn.execute(f"CREATE TABLE {table} (school_name TEXT PRIMARY KEY, payload TEXT)")
                school_rows = [
                    (name, json.dumps(payload, ensure_ascii=False))
                    for name, payload in source_data.get("schools", {}).items()
                ]
                conn.executemany(
                    f"INSERT INTO {table} (school_name, payload) VALUES (?, ?)",
                    school_rows,
                )
                continue
            rows = source_data
            if not isinstance(rows, list):
                continue
            columns = _columns_for(rows)
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            column_sql = ", ".join([f"{column} TEXT" for column in columns])
            conn.execute(f"CREATE TABLE {table} ({column_sql})")
            placeholders = ", ".join(["?"] * len(columns))
            column_names = ", ".join(columns)
            json_fields = config["json_fields"]
            values = [
                [
                    _encode_value(row.get(column), force_json=column in json_fields)
                    for column in columns
                ]
                for row in rows
            ]
            conn.executemany(
                f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})",
                values,
            )
        conn.commit()


def load_table(table: str, db_path: Path = DB_PATH) -> list[dict[str, Any]] | dict[str, Any]:
    config = TABLE_CONFIG[table]
    if table == "school_admissions_urls":
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(f"SELECT school_name, payload FROM {table}").fetchall()
        return {
            "schema_version": 1,
            "source_file": "school_admissions_urls.json",
            "description": "Loaded from SQLite database",
            "count": len(rows),
            "schools": {
                school_name: json.loads(payload)
                for school_name, payload in rows
            },
        }
    json_fields = config["json_fields"]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    decoded_rows = [
        {
            key: _decode_value(row[key], force_json=key in json_fields)
            for key in row.keys()
        }
        for row in rows
    ]
    return [
        {
            key: _restore_scalar_type(key, value)
            for key, value in decoded_row.items()
        }
        for decoded_row in decoded_rows
    ]


def database_available(db_path: Path = DB_PATH) -> bool:
    return db_path.exists()
