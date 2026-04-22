# SkillBridge Attendance API

A REST API for the SkillBridge state-level skilling programme, built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL** (SQLite for local dev). Role-based access control is enforced server-side on every protected endpoint.

---

## Live API

| | |
|---|---|
| **Base URL** | `https://skillbridge-api-sh5w.onrender.com` |
| **Interactive docs** | `https://skillbridge-api-sh5w.onrender.com/docs` |

### Quick smoke-test

```bash
curl -X POST https://skillbridge-api-sh5w.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"arjun@inst.sb","password":"Password123!"}'
```

---

## Local Setup (from scratch)

Assumes **Python 3.10+** and **pip** are installed.

```bash
# 1. Clone / unzip the project and cd into it
cd submission

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config
cp .env.example .env
# Edit .env if you want to point at a real PostgreSQL DB.
# By default it uses a local SQLite file (skillbridge.db) — no setup needed.

# 5. Seed the database with test data
python -m src.seed

# 6. Run the development server
uvicorn src.main:app --reload
# API is now at http://127.0.0.1:8000
# Swagger UI at http://127.0.0.1:8000/docs
```

---

## Test Accounts

All accounts use the password: **`Password123!`**

| Role | Email |
|---|---|
| Institution 1 | `sunrise@inst.sb` |
| Institution 2 | `greenfield@inst.sb` |
| Trainer 1 | `arjun@inst.sb` |
| Trainer 2 | `divya@inst.sb` |
| Trainer 3 | `suresh@inst.sb` |
| Trainer 4 | `lakshmi@inst.sb` |
| Student | `aishwarya@student.sb` |
| Programme Manager | `pm@skillbridge.sb` |
| Monitoring Officer | `monitor@skillbridge.sb` |

---

## Running Tests

```bash
pytest tests/ -v
```

All five tests hit a real SQLite test database (`test_skillbridge.db`) that is created and torn down automatically. No mocking of the database layer.

---

## Sample curl Commands

Replace `BASE` with your live URL or `http://127.0.0.1:8000` locally.  
Replace `TOKEN` with the JWT returned by login.

### Auth

```bash
# Signup
curl -X POST $BASE/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"New Trainer","email":"new@test.sb","password":"Pass123!","role":"trainer"}'

# Login (returns JWT)
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"arjun@inst.sb","password":"Password123!"}'

# Get monitoring-scoped token (Monitoring Officer only)
# Step 1: login as monitoring officer to get standard JWT
MONITOR_JWT=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"monitor@skillbridge.sb","password":"Password123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Step 2: exchange JWT + API key for scoped token
curl -X POST $BASE/auth/monitoring-token \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MONITOR_JWT" \
  -d '{"key":"monitor-secret-key-2024"}'
```

### Batches

```bash
# Create batch (trainer or institution)
TRAINER_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"arjun@inst.sb","password":"Password123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

INST_ID="<institution-id-from-seed-output>"

curl -X POST $BASE/batches \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"New Batch\",\"institution_id\":\"$INST_ID\"}"

# Generate invite link
BATCH_ID="<batch-id>"
curl -X POST $BASE/batches/$BATCH_ID/invite \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"expires_in_hours":48}'

# Student joins batch
STUDENT_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"aishwarya@student.sb","password":"Password123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST $BASE/batches/join \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"<invite-token>"}'
```

### Sessions

```bash
# Create session (trainer)
curl -X POST $BASE/sessions \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Morning Session\",\"date\":\"2025-10-01\",\"start_time\":\"09:00:00\",\"end_time\":\"11:00:00\",\"batch_id\":\"$BATCH_ID\"}"

# Get attendance for a session (trainer)
SESSION_ID="<session-id>"
curl -X GET $BASE/sessions/$SESSION_ID/attendance \
  -H "Authorization: Bearer $TRAINER_TOKEN"
```

### Attendance

```bash
# Mark attendance (student)
curl -X POST $BASE/attendance/mark \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"status\":\"present\"}"
```

### Summary Endpoints

```bash
# Batch summary (institution or programme manager)
INST_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sunrise@inst.sb","password":"Password123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X GET $BASE/batches/$BATCH_ID/summary \
  -H "Authorization: Bearer $INST_TOKEN"

# Institution summary (programme manager)
PM_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pm@skillbridge.sb","password":"Password123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X GET $BASE/institutions/$INST_ID/summary \
  -H "Authorization: Bearer $PM_TOKEN"

# Programme-wide summary (programme manager)
curl -X GET $BASE/programme/summary \
  -H "Authorization: Bearer $PM_TOKEN"
```

### Monitoring (scoped token required)

```bash
SCOPED_TOKEN="<monitoring-token-from-auth/monitoring-token>"

# Paginated — default 50 per page, max 500
curl -X GET "$BASE/monitoring/attendance?limit=50&offset=0" \
  -H "Authorization: Bearer $SCOPED_TOKEN"

# Verify 405 on write attempts
curl -X POST $BASE/monitoring/attendance \
  -H "Authorization: Bearer $SCOPED_TOKEN"
```

---

## JWT Payload Structure

### Standard access token (all roles, 24-hour expiry)

```json
{
  "user_id": "uuid",
  "role": "trainer",
  "email": "arjun@inst.sb",
  "token_type": "access",
  "iat": 1700000000,
  "exp": 1700086400
}
```

### Monitoring-scoped token (monitoring_officer only, 1-hour expiry)

```json
{
  "user_id": "uuid",
  "role": "monitoring_officer",
  "token_type": "monitoring",
  "iat": 1700000000,
  "exp": 1700003600
}
```

The `token_type` field is checked server-side: standard tokens are rejected at `/monitoring/attendance`, and monitoring tokens are rejected at all other endpoints.

---

## Schema Decisions

**`batch_trainers` (many-to-many join table)**  
A batch can have multiple trainers co-facilitating it, and a trainer can teach multiple batches simultaneously. A simple `trainer_id` column on `batches` would make co-facilitation impossible, so a join table is used. Composite primary key `(batch_id, trainer_id)` prevents duplicate assignments at the DB level.

**`batch_invites` with expiry and single-use tokens**  
Rather than sharing a permanent batch code, trainers generate time-limited tokens. Each token is single-use (`used = boolean`) so a leaked token can only be exploited once. The `created_by` field lets us audit which trainer issued which invite. In production, `used` would be set atomically using a `SELECT FOR UPDATE` lock to prevent race conditions.

**`institution_id` on `User`**  
Trainers and students belong to an institution. Storing this denormalised on the user row means a single FK lookup gives us the institution context without joining through batches every time.

**Dual-token approach for Monitoring Officer**  
The Monitoring Officer has read-only access to sensitive programme-wide data. A single password login gives them a standard `access` token (24h). To actually call `/monitoring/attendance`, they must additionally present a time-limited organisation API key via `POST /auth/monitoring-token`. This produces a separate `monitoring`-scoped token (1h). The endpoint validates `token_type == "monitoring"` explicitly, so even a valid standard token from a monitoring officer is rejected there. This mirrors API-key + short-lived session patterns used in production data access systems.

**DB indexes**  
Every foreign key column (`institution_id`, `batch_id`, `trainer_id`, `student_id`) has `index=True`. The `batch_invites.token` column is indexed because the invite-join hot path does a lookup by token on every `POST /batches/join`. The `attendance` table has a composite index on `(session_id, student_id)` which speeds up both the duplicate-mark check and the `GROUP BY` queries in the summary endpoints.

---

## Token Rotation and Revocation (production approach)

The current implementation is stateless: tokens are valid until expiry and cannot be revoked. In a real deployment I would:

1. Store a `token_version` integer on the `User` row. Include it in the JWT payload. On each request, compare the token's `token_version` against the DB. If they differ, reject with 401.
2. To revoke a user's tokens, increment their `token_version`. All outstanding JWTs immediately become invalid.
3. For the monitoring scoped token, maintain a short-lived Redis cache of issued token IDs (`jti` claim). On `POST /auth/monitoring-token`, write the JTI with a 1-hour TTL. On `/monitoring/attendance`, check the JTI exists in Redis before accepting.
4. Rotate the `SECRET_KEY` by maintaining two valid keys during the rotation window, phasing out the old one after all short-lived tokens expire.

---

## Known Security Issue

**Tokens cannot be revoked before expiry.** The API is stateless — once a JWT is issued, it remains valid until `exp` even if the user is deactivated or their password is changed. A compromised token for a monitoring officer is valid for a full hour.

**Fix with more time:** Add a `token_version` integer to the `User` model and include it in every JWT payload. On each authenticated request, compare the payload's version against the database row. Incrementing `token_version` instantly invalidates all outstanding tokens for that user with no need to maintain a blocklist. For the short-lived monitoring token specifically, a Redis-backed JTI allowlist (key per issued token, TTL = 1h) would allow single-use enforcement.

---

## Deployment Notes

Deployed to **Render** (free tier). Environment variables set via Render dashboard (never committed):
- `DATABASE_URL` — Neon PostgreSQL connection string
- `SECRET_KEY` — generated with `python -c "import secrets; print(secrets.token_hex(32))"`. The app **refuses to start** if this is missing or shorter than 32 characters.
- `MONITORING_API_KEY` — `monitor-secret-key-2024` (for testing)

On first deploy, the seed script was run manually via Render Shell:
```bash
python -m src.seed
```

Tables are auto-created by SQLAlchemy on startup (`Base.metadata.create_all`).

---

## What Works / What's Partial / What's Skipped

| Area | Status |
|---|---|
| All 15 endpoints | ✅ Fully implemented |
| Role-based access control on every endpoint | ✅ Server-side, extracted from JWT |
| JWT auth (signup, login) | ✅ bcrypt passwords, 24h tokens |
| Dual-token Monitoring Officer flow | ✅ Standard token + API key → scoped token |
| Validation (422 on bad fields, 404 on bad FKs, 403 on wrong role) | ✅ |
| 405 on POST to `/monitoring/attendance` | ✅ |
| Seed script (2 institutions, 4 trainers, 15 students, 3 batches, 8 sessions) | ✅ |
| All 5 pytest tests hitting real test DB | ✅ |
| Deployment to Render | ✅ |
| Pagination on monitoring endpoint | ✅ `?limit=50&offset=0` |
| N+1 queries eliminated | ✅ Summary endpoints use `GROUP BY` aggregation |
| SECRET_KEY startup validation | ✅ Raises `ValueError` if missing or < 32 chars |
| DB indexes on all FK columns | ✅ Including composite index on attendance |
| Token revocation | ❌ Stateless — see section above |
| Refresh tokens | ❌ Out of scope for this assignment |

---

## One Thing I'd Do Differently

I'd add **token revocation via `token_version`** from the start rather than leaving the API fully stateless. It's a one-column addition to the `User` model and a single integer comparison per request — almost zero overhead — but it closes the gap where a compromised token (especially the monitoring scoped token) remains valid until expiry with no way to invalidate it. It's the kind of thing that's trivial to add at the beginning and painful to retrofit once the system has active users.

---

## Project Structure

```
submission/
├── CONTACT.txt
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, router registration
│   ├── database.py      # SQLAlchemy engine + session
│   ├── models.py        # ORM models (with indexes)
│   ├── schemas.py       # Pydantic request/response models
│   ├── auth.py          # JWT creation, decoding, FastAPI dependencies
│   ├── seed.py          # Database seeding script
│   └── routers/
│       ├── auth.py
│       ├── batches.py
│       ├── sessions.py
│       ├── attendance.py
│       ├── institutions.py
│       ├── programme.py
│       └── monitoring.py
└── tests/
    ├── conftest.py      # TestClient + real SQLite fixture
    └── test_api.py      # 5 required tests
```
