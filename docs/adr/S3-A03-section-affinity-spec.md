# S3-A03 — Section Affinity Specification

## Section definitions

| code | label | description | typical evidence |
|---|---|---|---|
| background | Background | Applicant's foundational identity, education, and origin of expertise | Degrees, early career, field entry |
| experience | Professional Experience | Documented work history and professional roles | Job descriptions, employment letters, org charts |
| expert_opinion | Expert Opinion | Third-party expert assessments of applicant's standing | Letters of support, expert opinion letters |
| achievements | Achievements and Recognition | Concrete evidence of recognition, awards, publications | Awards, citations, publications, memberships |
| impact | Impact and Contributions | Evidence of applicant's measurable effect on their field or the US | Salary data, industry reports, policy alignment |
| conclusion | Conclusion | Summary narrative connecting evidence to NIW standard | Not evidence-driven — generated, not retrieved |

## Multi-section behavior

A chunk may have high affinity for more than one section. This is handled by allowing multiple `classification_results` rows per chunk — one per criterion-section pair. The LLM is asked to return the single best section affinity per criterion classification call. If a human reviewer believes a chunk belongs in a second section, they submit a `classification_feedback` row with `action=corrected` and a different `corrected_section_affinity_id`. Both the original and the correction are preserved.

## Confidence semantics

| Range | Meaning |
|---|---|
| 0.9 - 1.0 | Strong — use without human review |
| 0.7 - 0.89 | Moderate — flag for human review |
| 0.5 - 0.69 | Weak — require human confirmation before use in generation |
| < 0.5 | Not written — below threshold |

## Narrative routing behavior

Generation in Sprint 4 assembles each section by querying:
```sql
SELECT cr.*, c.text, c.chunk_index, dv.version_number, d.original_name
FROM classification_results cr
JOIN chunks c ON c.id = cr.chunk_id
JOIN document_versions dv ON dv.id = cr.document_version_id
JOIN documents d ON d.id = dv.document_id
WHERE cr.case_id = :case_id
AND cr.section_affinity_id = :section_id
AND cr.confidence_score >= :threshold
ORDER BY cr.confidence_score DESC
```

The `conclusion` section is generated without retrieved evidence — it is synthesized from the coverage summary and the other sections' content. This is the one section where retrieval does not drive generation.
