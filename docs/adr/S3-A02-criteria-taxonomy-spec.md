# S3-A02 — Legal Criteria Taxonomy Specification

## EB2 NIW seed data

| code | visa_type | label | display_order |
|---|---|---|---|
| EB2_NIW_C1 | EB2 | Substantial Merit and National Importance of the Endeavor | 1 |
| EB2_NIW_C2 | EB2 | Applicant is Well Positioned to Advance the Endeavor | 2 |
| EB2_NIW_C3 | EB2 | Benefit to USA Without Labor Certification | 3 |

## EB1 seed data

| code | visa_type | label | display_order |
|---|---|---|---|
| EB1_A | EB1 | Receipt of lesser nationally or internationally recognized prizes or awards | 1 |
| EB1_B | EB1 | Membership in associations requiring outstanding achievement | 2 |
| EB1_C | EB1 | Published material about the applicant in professional publications | 3 |
| EB1_D | EB1 | Participation as a judge of others' work | 4 |
| EB1_E | EB1 | Original scientific, scholarly, or business-related contributions | 5 |
| EB1_F | EB1 | Authorship of scholarly articles | 6 |
| EB1_G | EB1 | Display of work at artistic exhibitions or showcases | 7 |
| EB1_H | EB1 | Performance in a leading or critical role | 8 |
| EB1_I | EB1 | High salary relative to others in the field | 9 |
| EB1_J | EB1 | Commercial successes in the performing arts | 10 |

## Extensibility strategy

Criteria are seeded via Alembic migration data inserts — not hardcoded in application logic. New visa types (O-1, EB-3) are added by adding rows to `criteria_reference` with appropriate `visa_type` and `code` values. No code changes required for new criteria. `is_active=FALSE` deprecates a criterion without deletion. The classification service always queries `WHERE is_active=TRUE` to get current criteria.
