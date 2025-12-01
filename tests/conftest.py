# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

# Adjust these imports to match your actual structure
from services.inspect_worker.main import app as inspect_app
from services.classify_worker.main import app as classify_app
from services.act_worker.main import app as act_app


@pytest.fixture
def inspect_client():
    """FastAPI test client for the inspect worker."""
    return TestClient(inspect_app)


@pytest.fixture
def classify_client():
    """FastAPI test client for the classify worker."""
    return TestClient(classify_app)


@pytest.fixture
def act_client():
    """FastAPI test client for the act worker."""
    return TestClient(act_app)


@pytest.fixture
def sample_job_payload():
    """
    Example payload your workers receive.

    Adjust keys if your actual payload is different.
    """
    return {
        "job_id": "drbfo-uploads__uploads__3950_docx",
        "bucket": "drbfo-uploads",
        "blob": "uploads/INFO 4602 5602 -  Paper 6 Summary_vFinal.docx",
    }
