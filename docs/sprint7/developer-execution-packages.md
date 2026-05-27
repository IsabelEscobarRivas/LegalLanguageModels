# Developer Execution Packages

Sprint 7 implementation packages for the Developer on LegalLanguageModels, branch May26.

**Execution sequence:**

1. PO accepts ADR-011
2. Cursor runs 7A Package 1 (schema + review API)
3. QA signs off → Cursor runs 7A Package 2 (observability)
4. QA signs off → Sprint 7A closed
5. Cursor runs 7B Package 1 (attorney UI)
6. User 0 validation against MVP Acceptance Criteria
7. MVP closed when all acceptance criteria are checked

---

## Sprint 7A — Package 1: Review Schema + API

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 7A, Package 1.
Prerequisite: alembic current → 0013_kb_guidance_prompt_inst (head).
Read app/core/models.py and app/generation/router.py in full before writing.

---

TASK 1: Create migration 0014_review_export_schema.py

Create: alembic/versions/0014_review_export_schema.py
down_revision = "0013_kb_guidance_prompt_inst"

upgrade() creates these tables in order:

--- draft_section_reviews ---
CREATE TABLE draft_section_reviews (
    id VARCHAR(36) PRIMARY KEY,
    draft_section_id VARCHAR(36) NOT NULL
        REFERENCES draft_sections(id) ON DELETE RESTRICT,
    case_id VARCHAR(36) NOT NULL
        REFERENCES cases(id) ON DELETE RESTRICT,
    firm_id VARCHAR(36) NOT NULL
        REFERENCES firms(id) ON DELETE RESTRICT,
    reviewer_id VARCHAR(255) NOT NULL,
    action VARCHAR(30) NOT NULL,
    reviewer_edit TEXT,
    rejection_reason TEXT,
    regeneration_requested BOOLEAN NOT NULL DEFAULT false,
    regenerated_section_id VARCHAR(36)
        REFERENCES draft_sections(id),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
CHECK: action IN ('approved', 'rejected', 'edited')
Indexes: ix_draft_section_reviews_draft_section_id,
         ix_draft_section_reviews_case_id,
         ix_draft_section_reviews_firm_id

--- draft_exports ---
CREATE TABLE draft_exports (
    id VARCHAR(36) PRIMARY KEY,
    draft_output_id VARCHAR(36) NOT NULL
        REFERENCES draft_outputs(id) ON DELETE RESTRICT,
    case_id VARCHAR(36) NOT NULL
        REFERENCES cases(id) ON DELETE RESTRICT,
    firm_id VARCHAR(36) NOT NULL
        REFERENCES firms(id) ON DELETE RESTRICT,
    exported_by VARCHAR(255) NOT NULL,
    export_format VARCHAR(30) NOT NULL,
    section_snapshot JSONB NOT NULL,
    review_snapshot JSONB NOT NULL,
    s3_export_key VARCHAR(1000),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
CHECK: export_format IN ('json', 'txt', 'pdf')
Indexes: ix_draft_exports_draft_output_id,
         ix_draft_exports_case_id,
         ix_draft_exports_firm_id

downgrade() drops both tables in reverse order.

---

TASK 2: Add ORM models to app/core/models.py

Add after KBGuidanceTrace:

class DraftSectionReview(Base):
    __tablename__ = "draft_section_reviews"
    __table_args__ = (
        CheckConstraint(
            "action IN ('approved', 'rejected', 'edited')",
            name="ck_draft_section_reviews_action",
        ),
        {"info": {"append_only": True}},
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    draft_section_id = Column(String(36),
        ForeignKey("draft_sections.id", ondelete="RESTRICT",
            name="fk_draft_section_reviews_draft_section_id"),
        nullable=False, index=True)
    case_id = Column(String(36),
        ForeignKey("cases.id", ondelete="RESTRICT",
            name="fk_draft_section_reviews_case_id"),
        nullable=False, index=True)
    firm_id = Column(String(36),
        ForeignKey("firms.id", ondelete="RESTRICT",
            name="fk_draft_section_reviews_firm_id"),
        nullable=False, index=True)
    reviewer_id = Column(String(255), nullable=False)
    action = Column(String(30), nullable=False)
    reviewer_edit = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    regeneration_requested = Column(Boolean, nullable=False,
        default=False, server_default="false")
    regenerated_section_id = Column(String(36),
        ForeignKey("draft_sections.id"), nullable=True)
    created_at = Column(DateTime, nullable=False,
        default=datetime.utcnow, server_default=func.now())


class DraftExport(Base):
    __tablename__ = "draft_exports"
    __table_args__ = (
        CheckConstraint(
            "export_format IN ('json', 'txt', 'pdf')",
            name="ck_draft_exports_export_format",
        ),
        {"info": {"append_only": True}},
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    draft_output_id = Column(String(36),
        ForeignKey("draft_outputs.id", ondelete="RESTRICT",
            name="fk_draft_exports_draft_output_id"),
        nullable=False, index=True)
    case_id = Column(String(36),
        ForeignKey("cases.id", ondelete="RESTRICT",
            name="fk_draft_exports_case_id"),
        nullable=False, index=True)
    firm_id = Column(String(36),
        ForeignKey("firms.id", ondelete="RESTRICT",
            name="fk_draft_exports_firm_id"),
        nullable=False, index=True)
    exported_by = Column(String(255), nullable=False)
    export_format = Column(String(30), nullable=False)
    section_snapshot = Column(JSONB, nullable=False)
    review_snapshot = Column(JSONB, nullable=False)
    s3_export_key = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False,
        default=datetime.utcnow, server_default=func.now())

---

TASK 3: Create app/api/review/router.py

Endpoints:

POST /cases/{case_id}/drafts/{draft_id}/sections/{section_id}/review
Auth: require_case_access
Body:
  action: Literal["approved", "rejected", "edited"]
  reviewer_edit: Optional[str] = None  -- required when action="edited"
  rejection_reason: Optional[str] = None
  regeneration_requested: bool = False
Validation:
  - action="edited" requires reviewer_edit to be non-empty
  - action="approved" must have reviewer_edit=None
  - Confirm section belongs to draft, draft belongs to case
  - firm_id from claims
Status: 201
Returns: {review_id, draft_section_id, action, created_at}

GET /cases/{case_id}/drafts/{draft_id}/sections/{section_id}/reviews
Auth: require_case_access
Returns: list of all review rows for this section, newest first

GET /cases/{case_id}/drafts/{draft_id}/review-status
Auth: require_case_access
Returns: per-section review status summary
  {
    "draft_id": str,
    "sections": [
      {
        "section_id": str,
        "section_code": str,
        "latest_action": str | null,
        "reviewer_edit": str | null,
        "regeneration_requested": bool,
        "review_count": int
      }
    ],
    "export_eligible": bool  -- true when all sections approved or edited
  }

POST /cases/{case_id}/drafts/{draft_id}/sections/{section_id}/regenerate
Auth: require_case_access
Validation:
  - Latest review for section must have action="rejected"
  - regeneration_requested must be true on that review
Body:
  visa_type: Literal["EB1", "EB2"]
  force_generate: bool = True
Behavior:
  1. Fetch the original document_id and version_id from the draft_output
  2. Call generate_draft for the single section only
     (or call _generate_section directly if refactoring is minimal)
  3. On success, update the review row:
     regenerated_section_id = new_section.id
  4. Return new section content and traces
Status: 201

POST /cases/{case_id}/drafts/{draft_id}/export
Auth: require_case_access
Body:
  export_format: Literal["json", "txt"]
Validation:
  - All sections must have latest review action IN ('approved', 'edited')
  - No section may have latest action = 'rejected' without regenerated_section_id
Behavior:
  1. Build section_snapshot: for each section, use reviewer_edit if action='edited',
     else use generated content
  2. Build review_snapshot: current review state per section
  3. Insert DraftExport row
  4. Return export content inline (json or txt)
     For json: structured dict with sections, provenance metadata, review metadata
     For txt: plain text concatenation of section content in SECTION_ORDER
Status: 201
Returns: {export_id, export_format, content, created_at}

GET /cases/{case_id}/drafts/{draft_id}/exports
Auth: require_case_access
Returns: list of export records for this draft (content excluded — metadata only)

Register this router in app/main.py.

---

TASK 4: Apply migration and validate

alembic upgrade head → must show 0014_review_export_schema (head)

Confirm tables exist:
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('draft_section_reviews', 'draft_exports');
Must return 2 rows.

---

TASK 5: Commit

git add alembic/versions/0014_review_export_schema.py
git add app/core/models.py
git add app/api/review/
git add app/main.py
git commit -m "feat(review): reviewer workflow schema + API (Sprint 7A Package 1)

Migration 0014: draft_section_reviews, draft_exports tables.
Both tables are append-only — reviewer actions never mutate draft_sections.

Review endpoints: approve/reject/edit sections, regenerate rejected sections,
export approved drafts. Export validates all sections reviewed before allowing.
Section snapshot captures exact content at export time — immutable record."
git push origin May26

Stop. Report commit hash. Do not begin Package 2 until QA signs off.
```

---

## Sprint 7A — Package 2: Observability + Recovery

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 7A, Package 2.
Prerequisite: Package 1 committed and QA signed off.

---

TASK 1: Create app/api/observability/router.py

Endpoints for operational visibility without database access.

GET /observability/workflow/{case_id}
Auth: require_case_access
Returns full workflow state for a case:
  {
    "case_id": str,
    "documents": [
      {
        "document_id": str,
        "name": str,
        "lifecycle_state": str,
        "version_count": int,
        "latest_extraction_status": str | null
      }
    ],
    "drafts": [
      {
        "draft_id": str,
        "overall_status": str,
        "section_count": int,
        "sections_approved": int,
        "sections_rejected": int,
        "sections_pending": int,
        "export_eligible": bool,
        "created_at": str
      }
    ],
    "kb_documents": [
      {
        "kb_document_id": str,
        "title": str,
        "lifecycle_state": str,
        "chunk_count": int
      }
    ]
  }

GET /observability/invariants
Auth: get_current_claims (firm-scoped)
Runs all invariant checks from app/api/kb/invariants.py
Plus two new checks:

  -- Orphaned generation traces
  SELECT COUNT(*) FROM generation_traces gt
  WHERE NOT EXISTS (
      SELECT 1 FROM draft_sections ds WHERE ds.id = gt.draft_section_id
  );
  Must return 0.

  -- Exports with null review snapshot
  SELECT COUNT(*) FROM draft_exports
  WHERE review_snapshot IS NULL
    AND firm_id = :firm_id;
  Must return 0.

Returns all checks in a single response. Any violated check is flagged.

GET /observability/queue-health
Auth: get_current_claims
Returns ARQ Redis queue state:
  {
    "redis_connected": bool,
    "queue_name": "llm_tasks",
    "queued_jobs": int,
    "failed_jobs": int
  }
Use arq's RedisSettings to connect and inspect the queue.
If Redis is unreachable, return {"redis_connected": false} with 200 —
do not raise 503. Observability must not itself fail.

GET /observability/failed-lifecycles
Auth: get_current_claims (firm-scoped)
Returns all documents and KB documents in failed or stuck states:
  - Documents with lifecycle_state NOT IN ('indexed', 'final')
    AND created_at < now() - interval '1 hour'
  - KB documents with lifecycle_state NOT IN ('indexed')
    AND created_at < now() - interval '1 hour'
Returns:
  {
    "stuck_documents": [{document_id, name, lifecycle_state, created_at}],
    "stuck_kb_documents": [{kb_document_id, title, lifecycle_state, created_at}]
  }

Register in app/main.py.

---

TASK 2: Add dead-letter replay to app/workers/enqueue.py

Add:

async def replay_failed_job(
    pool,
    *,
    task_name: str,
    kwargs: dict,
) -> str:
    """Re-enqueue a failed task with the same kwargs.

    Caller is responsible for validating firm_id is present in kwargs
    before calling this. Never call without firm_id in kwargs.
    """
    job = await pool.enqueue_job(
        task_name,
        _queue_name="llm_tasks",
        **kwargs,
    )
    return job.job_id

Add endpoint to observability router:

POST /observability/replay
Auth: get_current_claims
Body:
  task_name: Literal["ingest_document", "ingest_kb_document",
                     "classify_document_version"]
  kwargs: dict
Validation:
  - kwargs must contain firm_id
  - kwargs["firm_id"] must match claims.firm_id
  - Reject if firm_id missing or mismatched — 403
Behavior:
  - Enqueue via replay_failed_job
  - Return {job_id, task_name, queued_at}
Status: 202

---

TASK 3: Commit

git add app/api/observability/
git add app/main.py
git add app/workers/enqueue.py
git commit -m "feat(observability): workflow state, invariant checks, queue health, dead-letter replay (Sprint 7A Package 2)

GET /observability/workflow/{case_id} — full case workflow state
GET /observability/invariants — all provenance + structural invariants
GET /observability/queue-health — ARQ Redis queue state
GET /observability/failed-lifecycles — stuck documents detection
POST /observability/replay — dead-letter task re-enqueue with firm validation"
git push origin May26

Stop. Report commit hash. Do not begin Sprint 7B until QA signs off on both 7A packages.
```

---

## Sprint 7B — Package 1: Attorney UI Foundation

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 7B, Package 1.
Prerequisite: Sprint 7A fully closed and QA signed off.
Read static/index.html and static/app.js in full before writing anything.
The existing UI is a React app served from FastAPI static files.
All new UI work extends this pattern — same React, same Tailwind, same static serving.
Do not introduce a build step, npm, or any new frontend toolchain.

---

CONTEXT

The existing UI (static/index.html + static/app.js) handles document ingestion.
Sprint 7B adds five screens to cover the full attorney workflow.
All screens are added to app.js as new React components.
Navigation between screens uses React state (no router library).

The five screens to build:

1. Case Dashboard
2. Draft Review Screen
3. Provenance Inspector (inline panel)
4. KB Guidance Visibility (inline on review screen)
5. Export Flow

---

TASK 1: Add API service methods to static/js/v2-api-service.js

Add these methods to the existing V2ApiService object:

// Review endpoints
submitReview: async (caseId, draftId, sectionId, body) =>
  fetch(`/cases/${caseId}/drafts/${draftId}/sections/${sectionId}/review`,
    {method:'POST', headers:{...auth, 'Content-Type':'application/json'},
     body: JSON.stringify(body)}),

getReviewStatus: async (caseId, draftId) =>
  fetch(`/cases/${caseId}/drafts/${draftId}/review-status`,
    {headers: auth}),

regenerateSection: async (caseId, draftId, sectionId, body) =>
  fetch(`/cases/${caseId}/drafts/${draftId}/sections/${sectionId}/regenerate`,
    {method:'POST', headers:{...auth, 'Content-Type':'application/json'},
     body: JSON.stringify(body)}),

exportDraft: async (caseId, draftId, format) =>
  fetch(`/cases/${caseId}/drafts/${draftId}/export`,
    {method:'POST', headers:{...auth, 'Content-Type':'application/json'},
     body: JSON.stringify({export_format: format})}),

getExports: async (caseId, draftId) =>
  fetch(`/cases/${caseId}/drafts/${draftId}/exports`,
    {headers: auth}),

// Observability
getWorkflowState: async (caseId) =>
  fetch(`/observability/workflow/${caseId}`, {headers: auth}),

getInvariants: async () =>
  fetch(`/observability/invariants`, {headers: auth}),

getQueueHealth: async () =>
  fetch(`/observability/queue-health`, {headers: auth}),

// KB
ingestKBDocument: async (kbDocumentId) =>
  fetch(`/kb/documents/${kbDocumentId}/ingest`,
    {method:'POST', headers: auth}),

// Draft
getDraft: async (caseId, draftId) =>
  fetch(`/cases/${caseId}/drafts/${draftId}`, {headers: auth}),

listDrafts: async (caseId) =>
  fetch(`/cases/${caseId}/drafts`, {headers: auth}),

Where auth = {'Authorization': `Bearer ${V2ApiService.getToken()}`}

---

TASK 2: Case Dashboard component

Add CaseDashboard component to app.js.

Displays:
- Case ref and visa type
- Document list with lifecycle_state badge (color-coded):
    received/ingested = gray
    chunked/embedded = yellow
    indexed = green
    failed = red
- KB Documents list with lifecycle_state badge and "Ingest" button
  (triggers POST /kb/documents/{id}/ingest, refreshes status)
- Drafts list with overall_status and a "Review" button per draft
- "Generate Draft" button (calls existing generate endpoint)
- Invariant health indicator: calls GET /observability/invariants,
  shows green checkmark if all ok, red warning if any violated

Refresh button to reload all state. Auto-refresh every 30 seconds.

---

TASK 3: Draft Review Screen component

Add DraftReviewScreen component.

Displays all 6 sections in order. For each section:

Section header:
  - section_code (formatted: "Background", "Experience", etc.)
  - Status badge: pending / approved / rejected / edited
  - KB guidance indicator: small tag "KB Guided" if kb_guidance_applied=true

Section content:
  - Generated text (or editor_edit if latest review action='edited')
  - "Show Provenance" button (opens ProvenanceInspector inline panel)

Review controls (shown below content):
  - [Approve] button → POST review with action='approved'
  - [Edit] button → shows textarea pre-filled with content,
    [Save Edit] submits action='edited' with reviewer_edit
  - [Reject + Regenerate] button → POST review with action='rejected',
    regeneration_requested=true, then auto-calls regenerate endpoint

After all sections approved/edited:
  - Export panel appears at bottom
  - [Export as JSON] and [Export as TXT] buttons
  - Shows export history

---

TASK 4: Provenance Inspector inline panel

When "Show Provenance" is clicked for a section, show an inline panel below the section content.

Panel displays:
  Evidence traces (from section.traces):
    For each trace:
      - citation_text (quoted)
      - source_document name
      - criteria_code
      - confidence_score (formatted as percentage)

  KB Guidance (if kb_guidance_applied=true):
    - Label: "KB Style Guidance Applied"
    - Subtext: "Guidance influences rhetoric only — not cited as evidence"
    - Count of kb_guidance_traces if available

  Visual separation:
    - Evidence traces in one card (blue border)
    - KB guidance indicator in separate card (purple border)
    - Clear visual distinction between the two

---

TASK 5: Commit

git add static/
git commit -m "feat(ui): attorney review UI — case dashboard, draft review, provenance inspector (Sprint 7B Package 1)

Case Dashboard: document lifecycle visibility, KB document management,
draft list with review navigation, invariant health indicator.

Draft Review Screen: section-by-section review with approve/edit/reject,
KB guidance indicator per section, regeneration trigger.

Provenance Inspector: inline panel showing citation_text, source document,
criteria code, confidence score. KB guidance visually separated from
evidence with explicit advisory label.

No build toolchain introduced — React + Tailwind via CDN, same pattern
as existing UI."
git push origin May26

Stop. Report commit hash. QA sign-off required before Sprint 7 is declared complete.
```
