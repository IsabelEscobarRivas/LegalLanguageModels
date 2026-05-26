# S4-A01 — Draft Generation Architecture Specification

## New tables

### `prompt_templates`

```sql
CREATE TABLE prompt_templates (
  id              VARCHAR(36)   PRIMARY KEY,
  visa_type       VARCHAR(20)   NOT NULL CHECK (visa_type IN ('EB1','EB2','BOTH')),
  section_code    VARCHAR(50)   NOT NULL,
  version         INTEGER       NOT NULL DEFAULT 1,
  is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
  system_prompt   TEXT          NOT NULL,
  user_prompt     TEXT          NOT NULL,
  model_name      VARCHAR(100)  NOT NULL DEFAULT 'gpt-4o',
  max_tokens      INTEGER       NOT NULL DEFAULT 1000,
  temperature     FLOAT         NOT NULL DEFAULT 0.3,
  examples          TEXT          NULL,
  created_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
  UNIQUE (visa_type, section_code, version)
);
CREATE INDEX ix_prompt_templates_visa_type ON prompt_templates(visa_type);
CREATE INDEX ix_prompt_templates_section_code ON prompt_templates(section_code);
CREATE INDEX ix_prompt_templates_active ON prompt_templates(is_active);
```

### `draft_outputs`

```sql
CREATE TABLE draft_outputs (
  id                  VARCHAR(36)   PRIMARY KEY,
  case_id             VARCHAR(36)   NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
  visa_type           VARCHAR(20)   NOT NULL CHECK (visa_type IN ('EB1','EB2')),
  document_version_id VARCHAR(36)   NOT NULL REFERENCES document_versions(id) ON DELETE RESTRICT,
  overall_status      VARCHAR(30)   NOT NULL CHECK (overall_status IN ('complete','incomplete','coverage_override')),
  coverage_summary    JSONB         NOT NULL,
  created_at          TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_draft_outputs_case_id ON draft_outputs(case_id);
```

draft_outputs is append-only. Each generation run creates a new row.

### `draft_sections`

```sql
CREATE TABLE draft_sections (
  id                  VARCHAR(36)   PRIMARY KEY,
  draft_output_id     VARCHAR(36)   NOT NULL REFERENCES draft_outputs(id) ON DELETE RESTRICT,
  section_code        VARCHAR(50)   NOT NULL,
  content             TEXT          NOT NULL,
  prompt_template_id  VARCHAR(36)   NOT NULL REFERENCES prompt_templates(id) ON DELETE RESTRICT,
  model_name          VARCHAR(100)  NOT NULL,
  model_version       VARCHAR(50)   NOT NULL,
  tokens_used         INTEGER       NULL,
  created_at          TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_draft_sections_draft_output_id ON draft_sections(draft_output_id);
CREATE INDEX ix_draft_sections_section_code ON draft_sections(section_code);
```

### `generation_traces`

```sql
CREATE TABLE generation_traces (
  id                        VARCHAR(36)   PRIMARY KEY,
  draft_section_id          VARCHAR(36)   NOT NULL REFERENCES draft_sections(id) ON DELETE RESTRICT,
  chunk_id                  VARCHAR(36)   NOT NULL REFERENCES chunks(id) ON DELETE RESTRICT,
  classification_result_id  VARCHAR(36)   NOT NULL REFERENCES classification_results(id) ON DELETE RESTRICT,
  citation_text             TEXT          NULL,
  similarity_score          FLOAT         NULL,
  created_at                TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_generation_traces_draft_section_id ON generation_traces(draft_section_id);
CREATE INDEX ix_generation_traces_chunk_id ON generation_traces(chunk_id);
CREATE INDEX ix_generation_traces_classification_result_id ON generation_traces(classification_result_id);
```

### `criteria_section_affinity_defaults`

```sql
CREATE TABLE criteria_section_affinity_defaults (
  id                    VARCHAR(36)   PRIMARY KEY,
  criteria_id           VARCHAR(36)   NOT NULL REFERENCES criteria_reference(id) ON DELETE RESTRICT,
  section_affinity_id   VARCHAR(36)   NOT NULL REFERENCES section_affinity_reference(id) ON DELETE RESTRICT,
  visa_type             VARCHAR(20)   NOT NULL CHECK (visa_type IN ('EB1','EB2','BOTH')),
  priority              INTEGER       NOT NULL DEFAULT 1,
  created_at            TIMESTAMP     NOT NULL DEFAULT NOW(),
  UNIQUE (criteria_id, section_affinity_id, visa_type)
);
CREATE INDEX ix_criteria_section_defaults_criteria_id ON criteria_section_affinity_defaults(criteria_id);
```

Seed data — EB2 NIW:

| criteria_code | section_code | priority |
|---|---|---|
| EB2_NIW_C1 | impact | 1 |
| EB2_NIW_C1 | achievements | 2 |
| EB2_NIW_C2 | experience | 1 |
| EB2_NIW_C2 | achievements | 2 |
| EB2_NIW_C3 | impact | 1 |
| EB2_NIW_C3 | conclusion | 2 |

Seed data — EB1:

| criteria_code | section_code | priority |
|---|---|---|
| EB1_A | achievements | 1 |
| EB1_B | achievements | 1 |
| EB1_C | expert_opinion | 1 |
| EB1_D | expert_opinion | 1 |
| EB1_E | achievements | 1 |
| EB1_F | achievements | 1 |
| EB1_G | achievements | 1 |
| EB1_H | experience | 1 |
| EB1_I | impact | 1 |
| EB1_J | impact | 1 |

---

## Generation workflow

```
1. Receive generate request: {case_id, document_id, version_id, visa_type, force_generate=False}
2. Validate JWT — verify case_id in claims
3. Run coverage evaluation (reuse Sprint 3 evaluate_coverage)
4. Coverage gate check:
   - If overall_status = 'incomplete' AND force_generate = False → return 422 with coverage gaps
   - If overall_status = 'incomplete' AND force_generate = True → proceed, set overall_status = 'coverage_override'
   - If overall_status = 'complete' → proceed normally
5. Create draft_output row
6. For each section in ['background','experience','expert_opinion','achievements','impact']:
   a. Query classification_results for this case/version filtered to this section_code
   b. Order by confidence_score DESC, take top 5
   c. Fetch active prompt_template for (visa_type, section_code)
   d. Build prompt — inject evidence as citation_text items
   e. Call OpenAI — store tokens_used
   f. Create draft_section row
   g. Create generation_trace rows — one per classification_result used
7. Generate conclusion section:
   - No retrieved evidence
   - Prompt receives coverage_summary + section summaries
   - Create draft_section row for conclusion
8. Return draft_output with all sections and traces
```

The conclusion section is always generated last and always from coverage summary — never from retrieved evidence. This is an invariant per ADR-005.

---

## Coverage gate behavior

```python
# force_generate=False (default)
if overall_status == 'incomplete':
    return {
        'status': 'coverage_incomplete',
        'missing_criteria': [...],
        'message': 'Generation blocked. Required criteria lack supporting evidence.',
        'override_available': True
    }  # HTTP 422

# force_generate=True
if overall_status == 'incomplete':
    overall_status = 'coverage_override'
    # proceed with warning in draft_output
```

---

## Prompt variable contract

Every section prompt receives these variables:

```python
{
    "visa_type": "EB2",
    "section_name": "Professional Experience",
    "applicant_name": "Felipe Cusnir",
    "evidence_items": [
        {
            "citation_text": "Designed the Anti-Money Laundering Program for leading payment institutions in Brazil, including Nubank, MercadoPago, and Zippi.",
            "criteria_code": "EB2_NIW_C2",
            "criteria_label": "Applicant is Well Positioned to Advance the Endeavor",
            "confidence_score": 0.85,
            "source_document": "Felipe_Cusnir_PP.pdf"
        }
    ],
    "examples": "Mr. Cusnir's decade of progressive experience...\n\n[second example paragraph]",  # nullable
    "section_instruction": "Write 2-3 paragraphs..."
}
```

Evidence items are serialized as a numbered list in the prompt:

```
1. "Designed the Anti-Money Laundering Program for Nubank, MercadoPago, and Zippi." (Felipe_Cusnir_PP.pdf, confidence: 0.85)
2. "Led complex financial crime investigations at BC Strategy Ltd." (Felipe_Cusnir_PP.pdf, confidence: 0.82)
```

---

## Draft immutability rules

draft_outputs, draft_sections, and generation_traces are all append-only. Re-generating creates new rows. Human feedback on drafts is deferred to Sprint 5 — no feedback table in Sprint 4.

---

## API contracts

### POST /cases/{case_id}/generate

Request:
```json
{
  "document_id": "uuid",
  "version_id": "uuid",
  "visa_type": "EB2",
  "force_generate": false
}
```

Response 202:
```json
{
  "draft_id": "uuid",
  "case_id": "uuid",
  "visa_type": "EB2",
  "overall_status": "complete",
  "coverage_summary": {},
  "sections": [
    {
      "section_code": "experience",
      "content": "Mr. Felipe Cusnir brings over ten years...",
      "citations_used": 3,
      "tokens_used": 412
    }
  ],
  "created_at": "2026-05-26T00:00:00Z"
}
```

Response 422 (coverage gate blocked):
```json
{
  "status": "coverage_incomplete",
  "missing_criteria": ["EB2_NIW_C3"],
  "override_available": true
}
```

### GET /cases/{case_id}/drafts

Response 200:
```json
{
  "case_id": "uuid",
  "drafts": [
    {
      "id": "uuid",
      "visa_type": "EB2",
      "overall_status": "complete",
      "section_count": 6,
      "created_at": "2026-05-26T00:00:00Z"
    }
  ]
}
```

### GET /cases/{case_id}/drafts/{draft_id}

Response 200:
```json
{
  "id": "uuid",
  "case_id": "uuid",
  "visa_type": "EB2",
  "overall_status": "complete",
  "coverage_summary": {},
  "sections": [
    {
      "id": "uuid",
      "section_code": "experience",
      "content": "...",
      "prompt_template_id": "uuid",
      "tokens_used": 412,
      "traces": [
        {
          "chunk_id": "uuid",
          "classification_result_id": "uuid",
          "citation_text": "Designed the Anti-Money Laundering Program...",
          "similarity_score": 0.87
        }
      ]
    }
  ],
  "created_at": "2026-05-26T00:00:00Z"
}
```
