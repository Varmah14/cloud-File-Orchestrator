# tests/test_act_worker.py


def test_act_worker_accepts_pubsub_payload(act_client, sample_job_payload):
    """
    Act worker should accept a valid payload and not crash.
    """
    resp = act_client.post(
        "/pubsub-push",
        json={"message": {"attributes": sample_job_payload}},
    )
    assert resp.status_code in (200, 204)
