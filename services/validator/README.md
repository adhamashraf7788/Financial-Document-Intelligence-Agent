# answer-validator-api

Checks whether an agent-generated answer is structurally valid and
arithmetically correct, before it's shown to the user. This is the single
source of truth for what counts as a "valid, grounded answer" in Project
LEDGER.

## Endpoint

```
POST /validate_answer
Content-Type: application/json
```

**Request body:** the raw answer JSON, in any of the 4 shapes below.

**Response body:**
```json
{ "valid": true, "message": "..." }
```
or
```json
{ "valid": false, "message": "..." }
```

`valid: false` is a normal, successful HTTP response (`200 OK`) — the
validator did its job correctly by rejecting a bad answer. Only a
genuinely malformed request would produce a different status code.

## The 4 accepted answer shapes

Every answer needs `answer_type`, `evidence`, and `params`. Example
payloads for all 4 live in `mock-data/answers/`.

| `answer_type` | `params` must have | `evidence` rule |
|---|---|---|
| `direct` | `value` (string or number) | ≥1 citation |
| `calculated` | `value` (number), `formula` (string) | ≥1 citation, and **the formula must actually evaluate to `value`** |
| `multi_span` | `values` (array, ≥2 items) | ≥1 citation |
| `insufficient_evidence` | `reason` (string) | optional, may be empty |

Each `evidence` citation needs a non-empty `document_id` and a `page`
greater than 0.

### Example: valid `calculated` answer

```json
{
  "answer_type": "calculated",
  "evidence": [
    { "document_id": "doc_041", "page": 2, "section": "Operating Expenses" }
  ],
  "params": { "value": 13.64, "formula": "(3875-3410)/3410*100" }
}
```

## Beyond basic schema checking

Two things this validator checks that a plain schema check wouldn't:

- **Arithmetic verification.** For `calculated` answers, the validator
  recomputes `formula` itself (using a sandboxed evaluator — no `eval()`
  on raw input) and rejects the answer if the result doesn't match the
  reported `value` within a small tolerance. This catches an answer that
  looks structurally fine but reports a number that doesn't actually
  follow from its own formula.
- **Evidence sanity.** `page` must be a positive integer and
  `document_id` must be non-empty — catches placeholder/garbage
  citations that would technically pass a bare type check.

## Running it

**Directly:**
```bash
cd services/validator
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**In Docker:**
```bash
# from the project root
docker build -t validator-service -f services/validator/Dockerfile .
docker run -p 8000:8000 validator-service
```

**Sending a test request (PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/validate_answer" `
  -Method Post -ContentType "application/json" `
  -Body (Get-Content -Raw mock-data/answers/direct.json)
```

## For orchestrator-api / integration

- Call `POST http://<validator-host>:8000/validate_answer` with the
  agent's raw answer JSON.
- Branch on the `valid` field in the response: `true` → forward to
  `ui-service`; `false` → the answer was rejected (see "What happens on
  rejection" below).
- The validator has **no dependency on any other service** — it's a
  pure function of the payload it's given, so it can be called and
  tested in isolation at any point.

### What happens on rejection

The validator does **not** retry or loop back to the agent itself — it
only reports pass/fail. If a retry-on-rejection flow is wanted, that
belongs in orchestrator/agent-service (see the service-flow diagram's
dashed retry loop from validator back to agent reasoning). Right now the
validator's `message` field on a rejection is a mix of hand-written text
and Pydantic's own raw error wording — **exact phrasing to match the
spec's example messages is still pending a team decision**; treat the
`message` string as informative but not yet stable.

## Testing

```bash
python -m pytest services/validator/tests/test_validation.py -v
python -m pytest shared/tests/test_schemas.py -v
```

Covers: all 4 answer types (valid + invalid), the arithmetic check
(including a rejected code-injection attempt), evidence sanity rules,
and the real HTTP layer via FastAPI's `TestClient`.
