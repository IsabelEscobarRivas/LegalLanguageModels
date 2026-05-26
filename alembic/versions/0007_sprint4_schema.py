"""Sprint 4 schema: citation_text, affinity defaults, generation tables

Revision ID: 0007_sprint4_schema
Revises: 0006_add_txt_extraction_method
Create Date: 2026-05-26

Adds citation_text to classification_results, criteria_section_affinity_defaults,
prompt_templates, draft_outputs, draft_sections, generation_traces, and seeds
visa-type-aware section affinity defaults.
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "0007_sprint4_schema"
down_revision = "0006_add_txt_extraction_method"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "classification_results",
        sa.Column("citation_text", sa.Text(), nullable=True),
    )

    op.create_table(
        "criteria_section_affinity_defaults",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "criteria_id",
            sa.String(36),
            sa.ForeignKey(
                "criteria_reference.id",
                ondelete="RESTRICT",
                name="fk_criteria_section_affinity_defaults_criteria_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "section_affinity_id",
            sa.String(36),
            sa.ForeignKey(
                "section_affinity_reference.id",
                ondelete="RESTRICT",
                name="fk_criteria_section_affinity_defaults_section_affinity_id",
            ),
            nullable=False,
        ),
        sa.Column("visa_type", sa.String(20), nullable=False),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "criteria_id",
            "section_affinity_id",
            "visa_type",
            name="uq_criteria_section_affinity_defaults_criteria_section_visa",
        ),
        sa.CheckConstraint(
            "visa_type IN ('EB1', 'EB2', 'BOTH')",
            name="ck_criteria_section_affinity_defaults_visa_type",
        ),
    )
    op.create_index(
        "ix_criteria_section_defaults_criteria_id",
        "criteria_section_affinity_defaults",
        ["criteria_id"],
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visa_type", sa.String(20), nullable=False),
        sa.Column("section_code", sa.String(50), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("examples", sa.Text(), nullable=True),
        sa.Column(
            "model_name",
            sa.String(100),
            nullable=False,
            server_default=sa.text("'gpt-4o'"),
        ),
        sa.Column(
            "max_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1000"),
        ),
        sa.Column(
            "temperature",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.3"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "visa_type",
            "section_code",
            "version",
            name="uq_prompt_templates_visa_type_section_code_version",
        ),
        sa.CheckConstraint(
            "visa_type IN ('EB1', 'EB2', 'BOTH')",
            name="ck_prompt_templates_visa_type",
        ),
    )
    op.create_index(
        "ix_prompt_templates_visa_type",
        "prompt_templates",
        ["visa_type"],
    )
    op.create_index(
        "ix_prompt_templates_section_code",
        "prompt_templates",
        ["section_code"],
    )
    op.create_index(
        "ix_prompt_templates_active",
        "prompt_templates",
        ["is_active"],
    )

    op.create_table(
        "draft_outputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_draft_outputs_case_id",
            ),
            nullable=False,
        ),
        sa.Column("visa_type", sa.String(20), nullable=False),
        sa.Column(
            "document_version_id",
            sa.String(36),
            sa.ForeignKey(
                "document_versions.id",
                ondelete="RESTRICT",
                name="fk_draft_outputs_document_version_id",
            ),
            nullable=False,
        ),
        sa.Column("overall_status", sa.String(30), nullable=False),
        sa.Column("coverage_summary", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "visa_type IN ('EB1', 'EB2')",
            name="ck_draft_outputs_visa_type",
        ),
        sa.CheckConstraint(
            "overall_status IN ('complete', 'incomplete', 'coverage_override')",
            name="ck_draft_outputs_overall_status",
        ),
    )
    op.create_index(
        "ix_draft_outputs_case_id",
        "draft_outputs",
        ["case_id"],
    )

    op.create_table(
        "draft_sections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "draft_output_id",
            sa.String(36),
            sa.ForeignKey(
                "draft_outputs.id",
                ondelete="RESTRICT",
                name="fk_draft_sections_draft_output_id",
            ),
            nullable=False,
        ),
        sa.Column("section_code", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "prompt_template_id",
            sa.String(36),
            sa.ForeignKey(
                "prompt_templates.id",
                ondelete="RESTRICT",
                name="fk_draft_sections_prompt_template_id",
            ),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_draft_sections_draft_output_id",
        "draft_sections",
        ["draft_output_id"],
    )
    op.create_index(
        "ix_draft_sections_section_code",
        "draft_sections",
        ["section_code"],
    )

    op.create_table(
        "generation_traces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "draft_section_id",
            sa.String(36),
            sa.ForeignKey(
                "draft_sections.id",
                ondelete="RESTRICT",
                name="fk_generation_traces_draft_section_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.String(36),
            sa.ForeignKey(
                "chunks.id",
                ondelete="RESTRICT",
                name="fk_generation_traces_chunk_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "classification_result_id",
            sa.String(36),
            sa.ForeignKey(
                "classification_results.id",
                ondelete="RESTRICT",
                name="fk_generation_traces_classification_result_id",
            ),
            nullable=False,
        ),
        sa.Column("citation_text", sa.Text(), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_generation_traces_draft_section_id",
        "generation_traces",
        ["draft_section_id"],
    )
    op.create_index(
        "ix_generation_traces_chunk_id",
        "generation_traces",
        ["chunk_id"],
    )
    op.create_index(
        "ix_generation_traces_classification_result_id",
        "generation_traces",
        ["classification_result_id"],
    )

    conn = op.get_bind()

    section_rows = conn.execute(
        text("SELECT id, code FROM section_affinity_reference")
    ).fetchall()
    section_map = {row[1]: row[0] for row in section_rows}

    criteria_rows = conn.execute(
        text("SELECT id, code FROM criteria_reference")
    ).fetchall()
    criteria_map = {row[1]: row[0] for row in criteria_rows}

    defaults = [
        ("EB2_NIW_C1", "impact", "EB2", 1),
        ("EB2_NIW_C1", "achievements", "EB2", 2),
        ("EB2_NIW_C2", "experience", "EB2", 1),
        ("EB2_NIW_C2", "achievements", "EB2", 2),
        ("EB2_NIW_C3", "impact", "EB2", 1),
        ("EB2_NIW_C3", "conclusion", "EB2", 2),
        ("EB1_A", "achievements", "EB1", 1),
        ("EB1_B", "achievements", "EB1", 1),
        ("EB1_C", "expert_opinion", "EB1", 1),
        ("EB1_D", "expert_opinion", "EB1", 1),
        ("EB1_E", "achievements", "EB1", 1),
        ("EB1_F", "achievements", "EB1", 1),
        ("EB1_G", "achievements", "EB1", 1),
        ("EB1_H", "experience", "EB1", 1),
        ("EB1_I", "impact", "EB1", 1),
        ("EB1_J", "impact", "EB1", 1),
    ]

    affinity_table = sa.table(
        "criteria_section_affinity_defaults",
        sa.column("id"),
        sa.column("criteria_id"),
        sa.column("section_affinity_id"),
        sa.column("visa_type"),
        sa.column("priority"),
    )

    op.bulk_insert(
        affinity_table,
        [
            {
                "id": str(uuid.uuid4()),
                "criteria_id": criteria_map[c],
                "section_affinity_id": section_map[s],
                "visa_type": v,
                "priority": p,
            }
            for c, s, v, p in defaults
            if c in criteria_map and s in section_map
        ],
    )


def downgrade() -> None:
    op.drop_table("generation_traces")
    op.drop_table("draft_sections")
    op.drop_table("draft_outputs")
    op.drop_table("prompt_templates")
    op.drop_table("criteria_section_affinity_defaults")
    op.drop_column("classification_results", "citation_text")
