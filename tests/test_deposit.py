import os
import uuid
import datetime as dt


def test_deposit_idempotency_and_interest_flow(tmp_path, monkeypatch):
    db_path = tmp_path / f"fintech_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    open_resp = client.post(
        "/deposit/accounts",
        json={
            "opened_on": "2026-01-01",
            "annual_interest_rate": "0.10",
            "day_count_basis": 365,
            "idempotency_key": "open-1",
        },
    )
    assert open_resp.status_code == 200
    account_id = open_resp.json()["id"]

    dep1 = client.post(
        f"/deposit/accounts/{account_id}/deposit",
        json={
            "amount": "100.00",
            "effective_date": "2026-01-01",
            "idempotency_key": "dep-1",
        },
    )
    assert dep1.status_code == 200

    dep2 = client.post(
        f"/deposit/accounts/{account_id}/deposit",
        json={
            "amount": "100.00",
            "effective_date": "2026-01-01",
            "idempotency_key": "dep-1",
        },
    )
    assert dep2.status_code == 200
    assert dep2.json()["current_balance"] == "100.00"

    acc = client.post(
        f"/deposit/accounts/{account_id}/accrue",
        json={"as_of_date": "2026-01-11"},
    )
    assert acc.status_code == 200

    acct_data = acc.json()
    assert acct_data["accrued_interest"] == "0.27"

    me = client.post(
        f"/deposit/accounts/{account_id}/month-end",
        json={"effective_date": "2026-01-31"},
    )
    assert me.status_code == 200
    assert me.json()["accrued_interest"] == "0.00"
    assert me.json()["current_balance"] == "100.27"
