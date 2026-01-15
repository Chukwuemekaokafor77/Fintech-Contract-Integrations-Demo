# Fintech Platform Integrations Demo

## What this is

Python mini-platform that demonstrates "contract-style" financial product logic plus integration patterns:

- Deposit account contract (deposit, withdraw, interest accrual, month-end posting)
- Loan contract (open/disburse, accrue interest, repay)
- Append-only domain events + ledger entries
- Outbox pattern with:
  - Queue delivery (stored in `queue_messages`)
  - Webhook delivery (HTTP) with retry/backoff

## Run locally

### Create venv + install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Run tests

```powershell
pytest -q
```

### Start API

```powershell
uvicorn app.main:app --reload --port 8001
```

Open:

- `http://127.0.0.1:8001/` (redirects to docs)
- `http://127.0.0.1:8001/docs`

## Demo flows (curl examples)

### Deposit account

1) Open

```bash
curl -X POST http://127.0.0.1:8001/deposit/accounts \
  -H "Content-Type: application/json" \
  -d '{"opened_on":"2026-01-01","annual_interest_rate":"0.10","day_count_basis":365,"idempotency_key":"open-1"}'
```

2) Deposit

```bash
curl -X POST http://127.0.0.1:8001/deposit/accounts/{account_id}/deposit \
  -H "Content-Type: application/json" \
  -d '{"amount":"100.00","effective_date":"2026-01-01","idempotency_key":"dep-1"}'
```

3) Accrue interest

```bash
curl -X POST http://127.0.0.1:8001/deposit/accounts/{account_id}/accrue \
  -H "Content-Type: application/json" \
  -d '{"as_of_date":"2026-01-11"}'
```

4) Month-end posting

```bash
curl -X POST http://127.0.0.1:8001/deposit/accounts/{account_id}/month-end \
  -H "Content-Type: application/json" \
  -d '{"effective_date":"2026-01-31"}'
```

### Loan

1) Open/disburse

```bash
curl -X POST http://127.0.0.1:8001/loan/accounts \
  -H "Content-Type: application/json" \
  -d '{"opened_on":"2026-01-01","principal":"1000.00","annual_interest_rate":"0.12","day_count_basis":365,"idempotency_key":"loan-open-1"}'
```

2) Accrue

```bash
curl -X POST http://127.0.0.1:8001/loan/accounts/{loan_id}/accrue \
  -H "Content-Type: application/json" \
  -d '{"as_of_date":"2026-01-31"}'
```

3) Repay

```bash
curl -X POST http://127.0.0.1:8001/loan/accounts/{loan_id}/repay \
  -H "Content-Type: application/json" \
  -d '{"amount":"200.00","effective_date":"2026-01-31","idempotency_key":"loan-pay-1"}'
```

### Integrations: outbox dispatch + replay

Create a webhook subscription:

```bash
curl -X POST http://127.0.0.1:8001/webhooks/subscriptions \
  -H "Content-Type: application/json" \
  -d '{"target_url":"https://example.com/webhook"}'
```

Dispatch pending outbox messages:

```bash
curl -X POST http://127.0.0.1:8001/outbox/dispatch \
  -H "Content-Type: application/json" \
  -d '{"max_messages":50}'
```

Replay/reset outbox messages:

```bash
curl -X POST http://127.0.0.1:8001/outbox/replay \
  -H "Content-Type: application/json" \
  -d '{"aggregate_type":"deposit_account"}'
```

