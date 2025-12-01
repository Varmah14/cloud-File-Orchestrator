# tests/test_inspect_worker.py


def test_inspect_worker_pubsub_push_accepts_payload(inspect_client, sample_job_payload):
    """
    Inspect worker should accept a valid job payload and return 204.
    """
    response = inspect_client.post("/pubsub-push", json=sample_job_payload)
    assert response.status_code in (200, 204)
