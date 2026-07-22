from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.core.config import DATABASE_URL

engine_kwargs = {"pool_pre_ping": True}
if make_url(DATABASE_URL).drivername.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _sqlite_column_definition(column) -> str:
    column_sql = f"{column.name} {column.type.compile(dialect=engine.dialect)}"
    if column.nullable is False:
        column_sql += " NOT NULL"

    default = column.default
    if default is not None and getattr(default, "is_scalar", False):
        default_value = default.arg
        if isinstance(default_value, str):
            default_sql = "'" + default_value.replace("'", "''") + "'"
        elif default_value is None:
            default_sql = "NULL"
        else:
            default_sql = str(default_value)
        column_sql += f" DEFAULT {default_sql}"

    return column_sql


def ensure_sqlite_schema() -> None:
    if not make_url(DATABASE_URL).drivername.startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                if column.primary_key:
                    continue
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {_sqlite_column_definition(column)}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
