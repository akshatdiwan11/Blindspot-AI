from app.core.config import Settings


def test_empty_database_url_falls_back_to_sqlite(tmp_path):
    s = Settings(database_url="  ", storage_dir=tmp_path, _env_file=None)
    assert s.database_kind == "sqlite"
    assert s.database_url == f"sqlite:///{(tmp_path / 'blindspot.db').resolve()}"


def test_hosted_postgres_urls_are_normalised(tmp_path):
    s = Settings(database_url="postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require", storage_dir=tmp_path, _env_file=None)
    assert s.database_kind == "postgresql"
    assert s.database_url == "postgresql+psycopg2://u:p@ep-x.neon.tech/neondb?sslmode=require"
    assert Settings(database_url="postgres://u:p@h/db", _env_file=None).database_url.startswith("postgresql+psycopg2://")
