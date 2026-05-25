# S3-A01 — Classification Architecture Specification

## New tables

### `criteria_reference`

```sql
CREATE TABLE criteria_reference (
  id              VARCHAR(36)   PRIMARY KEY,
  code            VARCHAR(50)   NOT NULL UNIQUE,
  visa_type       VARCHAR(20)   NOT NULL CHECK (visa_type IN ('EB1','EB2','BOTH')),
  label           VARCHAR(200)  NOT NULL,
  description     TEXT          NOT NULL,
  is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
  display_order   INTEGER       NOT NULL,
  created_at      TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_criteria_reference_visa_type ON criteria_reference(visa_type);
CREATE INDEX ix_criteria_reference_code ON criteria_reference(code);
```

### `section_affinity_reference`

```sql
CREATE TABLE section_affinity_reference (
  id            VARCHAR(36)  PRIMARY KEY,
  code          VARCHAR(50)  NOT NULL UNIQUE,
  label         VARCHAR(100) NOT NULL,
  description   TEXT         NOT NULL,
  display_order INTEGER      NOT NULL,
  created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
```

Seed data for `section_affinity_reference`:

| code | label | display_order |
|---|---|---|
| background | Background | 1 |
| experience | Professional Experience | 2 |
| expert_opinion | Expert Opinion | 3 |
| achievements | Achievements and Recognition | 4 |
| impact | Impact and Contributions | 5 |
| conclusion | Conclusion | 6 |

### `classification_results`

```sql
CREATE TABLE classification_results (
  id                    VARCHAR(36)   PRIMARY KEY,
  chunk_id              VARCHAR(36)   NOT NULL REFERENCES chunks(id) ON DELETE RESTRICT,
  document_version_id   VARCHAR(36)   NOT NULL REFERENCES document_versions(id) ON DELETE RESTRICT,
  case_id               VARCHAR(36)   NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
  criteria_id           VARCHAR(36)   NOT NULL REFERENCES criteria_reference(id) ON DELETE RESTRICT,
  section_affinity_id   VARCHAR(36)   NOT NULL REFERENCES section_affinity_reference(id) ON DELETE RESTRICT,
  confidence_score      FLOAT         NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
  rationale             TEXT          NOT NULL,
  model_name            VARCHAR(100)  NOT NULL,
  model_version         VARCHAR(50)   NOT NULL,
  classifier_type       VARCHAR(30)   NOT NULL CHECK (classifier_type IN ('llm','rule_based','hybrid')),
  created_at            TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_classification_results_chunk_id ON classification_results(chunk_id);
CREATE INDEX ix_classification_results_case_id ON classification_results(case_id);
CREATE INDEX ix_classification_results_criteria_id ON classification_results(criteria_id);
CREATE INDEX ix_classification_results_section_affinity_id ON classification_results(section_affinity_id);
CREATE INDEX ix_classification_results_document_version_id ON classification_results(document_version_id);
```

This table is append-only per ADR-003. No UPDATE or DELETE ever touches it.

One chunk can have multiple rows — one per criterion it supports. A chunk about salary evidence supporting both Criterion I (high salary) and Criterion H (critical role) produces two rows with different `criteria_id` values. This is the multi-label design.

### `classification_feedback`

```sql
CREATE TABLE classification_feedback (
  id                          VARCHAR(36)   PRIMARY KEY,
  classification_result_id    VARCHAR(36)   NOT NULL REFERENCES classification_results(id) ON DELETE RESTRICT,
  case_id                     VARCHAR(36)   NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
  reviewer_id                 VARCHAR(255)  NOT NULL,
  action                      VARCHAR(30)   NOT NULL CHECK (action IN ('confirmed','rejected','corrected')),
  corrected_criteria_id       VARCHAR(36)   NULL REFERENCES criteria_reference(id),
  corrected_section_affinity_id VARCHAR(36) NULL REFERENCES section_affinity_reference(id),
  corrected_confidence_score  FLOAT         NULL CHECK (corrected_confidence_score >= 0.0 AND corrected_confidence_score <= 1.0),
  rationale                   TEXT          NULL,
  created_at                  TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_classification_feedback_result_id ON classification_feedback(classification_result_id);
CREATE INDEX ix_classification_feedback_case_id ON classification_feedback(case_id);
```

### `coverage_gaps`

```sql
CREATE TABLE coverage_gaps (
  id              VARCHAR(36)   PRIMARY KEY,
  case_id         VARCHAR(36)   NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
  criteria_id     VARCHAR(36)   NOT NULL REFERENCES criteria_reference(id) ON DELETE RESTRICT,
  gap_status      VARCHAR(30)   NOT NULL CHECK (gap_status IN ('covered','insufficient','missing')),
  chunk_count     INTEGER       NOT NULL DEFAULT 0,
  evaluated_at    TIMESTAMP     NOT NULL DEFAULT NOW(),
  UNIQUE (case_id, criteria_id)
);
CREATE INDEX ix_coverage_gaps_case_id ON coverage_gaps(case_id);
```

`UNIQUE (case_id, criteria_id)` — one coverage record per criterion per case, updated on each coverage evaluation. This table is NOT append-only — it represents current coverage state.

---

## Classification flow

```
1. Receive classify request: {case_id, chunk_id, version_id}
2. Validate JWT — verify case_id in claims
3. Fetch chunk text from DB
4. Fetch active criteria_reference rows for case visa_type
5. For each criterion: call LLM classifier
   - Input: chunk text + criterion label + criterion description
   - Output: {supports: bool, confidence: float, rationale: str, section_affinity: code}
6. For each criterion where supports=True AND confidence >= threshold:
   - Resolve section_affinity_id from section_affinity_reference
   - Insert classification_results row
7. Write classification_completed ProcessingEvent
8. Return classification summary
```

Threshold for writing a result: `confidence >= 0.5` (configurable via `CLASSIFICATION_CONFIDENCE_THRESHOLD` env var, default 0.5).

---

## LLM classifier prompt contract

The classification service sends one LLM call per criterion per chunk. The prompt must elicit structured JSON output:

```json
{
  "supports": true,
  "confidence": 0.85,
  "rationale": "The chunk describes peer-reviewed publications cited by 47 researchers, directly evidencing scholarly contributions.",
  "section_affinity": "achievements"
}
```

Model: `gpt-4o` (configurable via `CLASSIFICATION_MODEL` env var). Temperature: 0. JSON mode enforced via `response_format={"type": "json_object"}`.

---

## API contracts

### POST /cases/{case_id}/chunks/{chunk_id}/classify

Request:
```json
{
  "visa_type": "EB2",
  "force_reclassify": false
}
```

Response 202:
```json
{
  "chunk_id": "uuid",
  "classifications_created": 3,
  "classifications": [
    {
      "id": "uuid",
      "criteria_code": "EB2_NIW_C1",
      "criteria_label": "Substantial Merit and National Importance",
      "section_affinity": "achievements",
      "confidence_score": 0.85,
      "rationale": "..."
    }
  ]
}
```

`force_reclassify=true` creates new rows even if classifications already exist for this chunk. `force_reclassify=false` returns existing classifications if present (idempotency).

Errors: 404 if chunk not found. 422 if visa_type invalid. 503 if LLM call fails.

### POST /cases/{case_id}/classify-version

Classify all chunks for the latest document version in a case. Bulk operation.

Request:
```json
{
  "document_id": "uuid",
  "version_id": "uuid",
  "visa_type": "EB2",
  "force_reclassify": false
}
```

Response 202:
```json
{
  "version_id": "uuid",
  "chunks_processed": 14,
  "classifications_created": 31,
  "chunks_with_no_match": 3
}
```

### POST /cases/{case_id}/classifications/{classification_result_id}/feedback

Request:
```json
{
  "action": "corrected",
  "corrected_criteria_id": "uuid",
  "corrected_section_affinity_id": "uuid",
  "corrected_confidence_score": 0.9,
  "rationale": "This chunk describes salary benchmarking, not peer recognition."
}
```

Response 201:
```json
{
  "id": "uuid",
  "classification_result_id": "uuid",
  "action": "corrected",
  "created_at": "2026-05-25T00:00:00Z"
}
```

### GET /cases/{case_id}/coverage

Response 200:
```json
{
  "case_id": "uuid",
  "visa_type": "EB2",
  "coverage": [
    {
      "criteria_id": "uuid",
      "criteria_code": "EB2_NIW_C1",
      "criteria_label": "Substantial Merit and National Importance",
      "gap_status": "covered",
      "chunk_count": 4
    },
    {
      "criteria_id": "uuid",
      "criteria_code": "EB2_NIW_C3",
      "criteria_label": "Benefit to USA Without Labor Certification",
      "gap_status": "missing",
      "chunk_count": 0
    }
  ],
  "overall_status": "incomplete",
  "evaluated_at": "2026-05-25T00:00:00Z"
}
```

`overall_status`: `complete` if all criteria are `covered`, `incomplete` otherwise.
