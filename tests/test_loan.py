import uuid


def test_loan_open_accrue_and_repay(tmp_path, monkeypatch):
    db_path = tmp_path / f"fintech_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    open_resp = client.post(
        "/loan/accounts",
        json={
            "opened_on": "2026-01-01",
            "principal": "1000.00",
            "annual_interest_rate": "0.12",
            "day_count_basis": 365,
            "idempotency_key": "loan-open-1",
        },
    )
    assert open_resp.status_code == 200
    loan_id = open_resp.json()["id"]
    assert open_resp.json()["outstanding_principal"] == "1000.00"

    acc = client.post(f"/loan/accounts/{loan_id}/accrue", json={"as_of_date": "2026-01-31"})
    assert acc.status_code == 200

    repay = client.post(
        f"/loan/accounts/{loan_id}/repay",
        json={
            "amount": "200.00",
            "effective_date": "2026-01-31",
            "idempotency_key": "loan-pay-1",
        },
    )
    assert repay.status_code == 200

    repay2 = client.post(
        f"/loan/accounts/{loan_id}/repay",
        json={
            "amount": "200.00",
            "effective_date": "2026-01-31",
            "idempotency_key": "loan-pay-1",
        },
    )
    assert repay2.status_code == 200
    assert repay2.json() == repay.json()
