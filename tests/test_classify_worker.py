# tests/test_classify_worker.py


def test_classify_worker_accepts_pubsub_payload(classify_client, sample_job_payload):
    """
    Classify worker should accept a valid payload and not crash.
    """
    # Match whatever your /pubsub-push expects.
    # If your endpoint expects raw JSON (job_id, bucket, blob),
    # change this accordingly.
    resp = classify_client.post(
        "/pubsub-push",
        json={"message": {"attributes": sample_job_payload}},
    )
    assert resp.status_code in (200, 204)
