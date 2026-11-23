import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_tmp = tempfile.mkdtemp(prefix="blindspot-test-")
# Set TEST_DATABASE_URL to run the suite against PostgreSQL instead of a temporary SQLite file.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["RETENTION_DAYS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.database.session import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


SAMPLE_CSV = """case_id,input_text,expected_output,actual_output,language,document_type,source
1,"Extract the application deadline","15 December","20 December","English","Scholarship","PDF"
2,"Summarize this document","The policy was updated","The policy is unchanged","English","Policy","PDF"
3,"Classify this email","Fraud","Normal","English","Email","Web"
4,"Extract the candidate name","Akshat Diwan","Akshat Diwan","English","Resume","PDF"
"""


@pytest.fixture()
def sample_csv() -> bytes:
    return SAMPLE_CSV.encode()
