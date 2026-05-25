"""classification schema: reference tables, classification results, feedback, coverage

Revision ID: 0005_classification_schema
Revises: 0004_min_similarity
Create Date: 2026-05-25

Creates criteria_reference, section_affinity_reference, classification_results,
classification_feedback, and coverage_gaps. Seeds section affinity and EB1/EB2
criteria reference rows via bulk_insert.
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = "0005_classification_schema"
down_revision = "0004_min_similarity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "criteria_reference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("visa_type", sa.String(20), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_criteria_reference_code"),
        sa.CheckConstraint(
            "visa_type IN ('EB1', 'EB2', 'BOTH')",
            name="ck_criteria_reference_visa_type",
        ),
    )
    op.create_index(
        "ix_criteria_reference_visa_type",
        "criteria_reference",
        ["visa_type"],
    )
    op.create_index("ix_criteria_reference_code", "criteria_reference", ["code"])

    op.create_table(
        "section_affinity_reference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_section_affinity_reference_code"),
    )

    op.create_table(
        "classification_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.String(36),
            sa.ForeignKey(
                "chunks.id",
                ondelete="RESTRICT",
                name="fk_classification_results_chunk_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            sa.String(36),
            sa.ForeignKey(
                "document_versions.id",
                ondelete="RESTRICT",
                name="fk_classification_results_document_version_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_classification_results_case_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "criteria_id",
            sa.String(36),
            sa.ForeignKey(
                "criteria_reference.id",
                ondelete="RESTRICT",
                name="fk_classification_results_criteria_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "section_affinity_id",
            sa.String(36),
            sa.ForeignKey(
                "section_affinity_reference.id",
                ondelete="RESTRICT",
                name="fk_classification_results_section_affinity_id",
            ),
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("classifier_type", sa.String(30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_classification_results_confidence_score",
        ),
        sa.CheckConstraint(
            "classifier_type IN ('llm', 'rule_based', 'hybrid')",
            name="ck_classification_results_classifier_type",
        ),
    )
    op.create_index(
        "ix_classification_results_chunk_id",
        "classification_results",
        ["chunk_id"],
    )
    op.create_index(
        "ix_classification_results_case_id",
        "classification_results",
        ["case_id"],
    )
    op.create_index(
        "ix_classification_results_criteria_id",
        "classification_results",
        ["criteria_id"],
    )
    op.create_index(
        "ix_classification_results_section_affinity_id",
        "classification_results",
        ["section_affinity_id"],
    )
    op.create_index(
        "ix_classification_results_document_version_id",
        "classification_results",
        ["document_version_id"],
    )

    op.create_table(
        "classification_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "classification_result_id",
            sa.String(36),
            sa.ForeignKey(
                "classification_results.id",
                ondelete="RESTRICT",
                name="fk_classification_feedback_classification_result_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_classification_feedback_case_id",
            ),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column(
            "corrected_criteria_id",
            sa.String(36),
            sa.ForeignKey(
                "criteria_reference.id",
                name="fk_classification_feedback_corrected_criteria_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "corrected_section_affinity_id",
            sa.String(36),
            sa.ForeignKey(
                "section_affinity_reference.id",
                name="fk_classification_feedback_corrected_section_affinity_id",
            ),
            nullable=True,
        ),
        sa.Column("corrected_confidence_score", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('confirmed', 'rejected', 'corrected')",
            name="ck_classification_feedback_action",
        ),
        sa.CheckConstraint(
            "corrected_confidence_score IS NULL OR "
            "(corrected_confidence_score >= 0.0 AND corrected_confidence_score <= 1.0)",
            name="ck_classification_feedback_corrected_confidence_score",
        ),
    )
    op.create_index(
        "ix_classification_feedback_result_id",
        "classification_feedback",
        ["classification_result_id"],
    )
    op.create_index(
        "ix_classification_feedback_case_id",
        "classification_feedback",
        ["case_id"],
    )

    op.create_table(
        "coverage_gaps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_coverage_gaps_case_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "criteria_id",
            sa.String(36),
            sa.ForeignKey(
                "criteria_reference.id",
                ondelete="RESTRICT",
                name="fk_coverage_gaps_criteria_id",
            ),
            nullable=False,
        ),
        sa.Column("gap_status", sa.String(30), nullable=False),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "evaluated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "case_id",
            "criteria_id",
            name="uq_coverage_gaps_case_id_criteria_id",
        ),
        sa.CheckConstraint(
            "gap_status IN ('covered', 'insufficient', 'missing')",
            name="ck_coverage_gaps_gap_status",
        ),
    )
    op.create_index("ix_coverage_gaps_case_id", "coverage_gaps", ["case_id"])

    section_affinity_reference = sa.table(
        "section_affinity_reference",
        sa.column("id", sa.String(36)),
        sa.column("code", sa.String(50)),
        sa.column("label", sa.String(100)),
        sa.column("description", sa.Text()),
        sa.column("display_order", sa.Integer()),
    )
    op.bulk_insert(
        section_affinity_reference,
        [
            {
                "id": str(uuid.uuid4()),
                "code": "background",
                "label": "Background",
                "description": "Applicant foundational identity, education, and origin of expertise",
                "display_order": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "experience",
                "label": "Professional Experience",
                "description": "Documented work history and professional roles",
                "display_order": 2,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "expert_opinion",
                "label": "Expert Opinion",
                "description": "Third-party expert assessments of applicant standing",
                "display_order": 3,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "achievements",
                "label": "Achievements and Recognition",
                "description": "Concrete evidence of recognition, awards, publications",
                "display_order": 4,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "impact",
                "label": "Impact and Contributions",
                "description": "Evidence of measurable effect on field or USA",
                "display_order": 5,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "conclusion",
                "label": "Conclusion",
                "description": "Summary narrative — generated not retrieved",
                "display_order": 6,
            },
        ],
    )

    criteria_reference = sa.table(
        "criteria_reference",
        sa.column("id", sa.String(36)),
        sa.column("code", sa.String(50)),
        sa.column("visa_type", sa.String(20)),
        sa.column("label", sa.String(200)),
        sa.column("description", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("display_order", sa.Integer()),
    )
    op.bulk_insert(
        criteria_reference,
        [
            {
                "id": str(uuid.uuid4()),
                "code": "EB2_NIW_C1",
                "visa_type": "EB2",
                "label": "Substantial Merit and National Importance of the Endeavor",
                "description": "The proposed endeavor has both substantial merit and national importance",
                "is_active": True,
                "display_order": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB2_NIW_C2",
                "visa_type": "EB2",
                "label": "Applicant is Well Positioned to Advance the Endeavor",
                "description": "The applicant is well positioned to advance the proposed endeavor",
                "is_active": True,
                "display_order": 2,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB2_NIW_C3",
                "visa_type": "EB2",
                "label": "Benefit to USA Without Labor Certification",
                "description": "On balance it would be beneficial to the USA to waive the labor certification requirement",
                "is_active": True,
                "display_order": 3,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_A",
                "visa_type": "EB1",
                "label": "Receipt of lesser nationally or internationally recognized prizes or awards for excellence",
                "description": "Evidence of prizes or awards for excellence in the field",
                "is_active": True,
                "display_order": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_B",
                "visa_type": "EB1",
                "label": "Membership in associations requiring outstanding achievement",
                "description": "Membership in associations that require outstanding achievement of their members",
                "is_active": True,
                "display_order": 2,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_C",
                "visa_type": "EB1",
                "label": "Published material about the applicant in professional publications",
                "description": "Published material about the alien in professional or major trade publications or other major media",
                "is_active": True,
                "display_order": 3,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_D",
                "visa_type": "EB1",
                "label": "Participation as a judge of others work",
                "description": "Participation on a panel or individually as a judge of the work of others",
                "is_active": True,
                "display_order": 4,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_E",
                "visa_type": "EB1",
                "label": "Original scientific scholarly or business-related contributions of major significance",
                "description": "Evidence of original scientific scholarly artistic athletic or business-related contributions of major significance",
                "is_active": True,
                "display_order": 5,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_F",
                "visa_type": "EB1",
                "label": "Authorship of scholarly articles",
                "description": "Evidence of authorship of scholarly articles in professional or major trade publications",
                "is_active": True,
                "display_order": 6,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_G",
                "visa_type": "EB1",
                "label": "Display of work at artistic exhibitions or showcases",
                "description": "Evidence that the aliens work has been displayed at artistic exhibitions or showcases",
                "is_active": True,
                "display_order": 7,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_H",
                "visa_type": "EB1",
                "label": "Performance in a leading or critical role",
                "description": "Evidence that the alien has performed in a leading or critical role for organizations with distinguished reputations",
                "is_active": True,
                "display_order": 8,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_I",
                "visa_type": "EB1",
                "label": "High salary relative to others in the field",
                "description": "Evidence that the alien has commanded a high salary or remuneration in relation to others in the field",
                "is_active": True,
                "display_order": 9,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "EB1_J",
                "visa_type": "EB1",
                "label": "Commercial successes in the performing arts",
                "description": "Evidence of commercial successes in the performing arts",
                "is_active": True,
                "display_order": 10,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("coverage_gaps")
    op.drop_table("classification_feedback")
    op.drop_table("classification_results")
    op.drop_table("section_affinity_reference")
    op.drop_table("criteria_reference")
