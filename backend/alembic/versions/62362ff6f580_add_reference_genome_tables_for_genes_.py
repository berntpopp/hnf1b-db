"""add reference genome tables for genes, transcripts, domains, and exons

Creates tables for storing genomic reference data:
- reference_genomes: Genome assemblies (GRCh37, GRCh38, T2T-CHM13)
- genes: Gene annotations (HNF1B and chr17q12 region)
- transcripts: Transcript isoforms (RefSeq, Ensembl)
- exons: Exon genomic coordinates
- protein_domains: Protein domain annotations (UniProt/Pfam/InterPro)

Resolves: #96 (Phase 1 - Backend Infrastructure)

Revision ID: 62362ff6f580
Revises: 30848634d515
Create Date: 2025-11-18 11:23:10.491848

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = '62362ff6f580'
down_revision: Union[str, Sequence[str], None] = '30848634d515'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create reference genome tables."""

    # 1. Create reference_genomes table
    op.create_table(
        'reference_genomes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True,
                  comment="Assembly name (e.g., 'GRCh38', 'hg38')"),
        sa.Column('ucsc_name', sa.String(50),
                  comment="UCSC genome browser name (e.g., 'hg38', 'hg19')"),
        sa.Column('ensembl_name', sa.String(50),
                  comment="Ensembl assembly name"),
        sa.Column('ncbi_name', sa.String(100),
                  comment="NCBI assembly accession"),
        sa.Column('version', sa.String(20),
                  comment="Assembly version/patch (e.g., 'p14')"),
        sa.Column('release_date', sa.DateTime(timezone=True),
                  comment="Official release date"),
        sa.Column('is_default', sa.Boolean, default=False, nullable=False,
                  comment="Whether this is the default assembly for API queries"),
        sa.Column('source_url', sa.Text,
                  comment="URL to assembly information page"),
        sa.Column('extra_data', JSONB,
                  comment="Additional assembly extra_data"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_reference_genomes_name', 'reference_genomes', ['name'])
    op.create_index('ix_reference_genomes_is_default', 'reference_genomes', ['is_default'])

    # 2. Create genes table
    op.create_table(
        'genes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('symbol', sa.String(50), nullable=False,
                  comment="Gene symbol (e.g., 'HNF1B')"),
        sa.Column('name', sa.String(255), nullable=False,
                  comment="Full gene name"),
        sa.Column('chromosome', sa.String(10), nullable=False,
                  comment="Chromosome (e.g., '17', 'X', 'MT')"),
        sa.Column('start', sa.Integer, nullable=False,
                  comment="Genomic start position (1-based, inclusive)"),
        sa.Column('end', sa.Integer, nullable=False,
                  comment="Genomic end position (1-based, inclusive)"),
        sa.Column('strand', sa.String(1), nullable=False,
                  comment="DNA strand ('+' or '-')"),
        sa.Column('genome_id', UUID(as_uuid=True), nullable=False),
        sa.Column('ensembl_id', sa.String(50),
                  comment="Ensembl gene ID"),
        sa.Column('ncbi_gene_id', sa.String(50),
                  comment="NCBI Gene ID"),
        sa.Column('hgnc_id', sa.String(50),
                  comment="HGNC ID"),
        sa.Column('omim_id', sa.String(50),
                  comment="OMIM ID"),
        sa.Column('source', sa.String(50), nullable=False,
                  comment="Data source (e.g., 'NCBI Gene', 'Ensembl')"),
        sa.Column('source_version', sa.String(50),
                  comment="Source database version"),
        sa.Column('source_url', sa.Text,
                  comment="URL to source record"),
        sa.Column('extra_data', JSONB,
                  comment="Additional gene extra_data"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['genome_id'], ['reference_genomes.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_genes_symbol', 'genes', ['symbol'])
    op.create_index('ix_genes_chromosome', 'genes', ['chromosome'])
    op.create_index('ix_genes_start', 'genes', ['start'])
    op.create_index('ix_genes_end', 'genes', ['end'])
    op.create_index('ix_genes_genome_id', 'genes', ['genome_id'])
    op.create_index('ix_genes_ensembl_id', 'genes', ['ensembl_id'])
    op.create_index('ix_genes_ncbi_gene_id', 'genes', ['ncbi_gene_id'])
    op.create_index('ix_genes_hgnc_id', 'genes', ['hgnc_id'])

    # 3. Create transcripts table
    op.create_table(
        'transcripts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('transcript_id', sa.String(50), nullable=False, unique=True,
                  comment="RefSeq or Ensembl transcript ID"),
        sa.Column('protein_id', sa.String(50),
                  comment="RefSeq protein ID (e.g., 'NP_000449.3')"),
        sa.Column('is_canonical', sa.Boolean, default=False, nullable=False,
                  comment="Whether this is the canonical transcript"),
        sa.Column('cds_start', sa.Integer,
                  comment="CDS start position (genomic coordinates)"),
        sa.Column('cds_end', sa.Integer,
                  comment="CDS end position (genomic coordinates)"),
        sa.Column('exon_count', sa.Integer, nullable=False,
                  comment="Number of exons"),
        sa.Column('gene_id', UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(50), nullable=False,
                  comment="Data source (e.g., 'RefSeq', 'Ensembl')"),
        sa.Column('source_url', sa.Text,
                  comment="URL to transcript record"),
        sa.Column('extra_data', JSONB,
                  comment="Additional transcript extra_data"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['gene_id'], ['genes.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_transcripts_transcript_id', 'transcripts', ['transcript_id'])
    op.create_index('ix_transcripts_protein_id', 'transcripts', ['protein_id'])
    op.create_index('ix_transcripts_is_canonical', 'transcripts', ['is_canonical'])
    op.create_index('ix_transcripts_gene_id', 'transcripts', ['gene_id'])

    # 4. Create exons table
    op.create_table(
        'exons',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('exon_number', sa.Integer, nullable=False,
                  comment="Exon number (1-based)"),
        sa.Column('chromosome', sa.String(10), nullable=False,
                  comment="Chromosome (denormalized from gene)"),
        sa.Column('start', sa.Integer, nullable=False,
                  comment="Exon start position (genomic, 1-based inclusive)"),
        sa.Column('end', sa.Integer, nullable=False,
                  comment="Exon end position (genomic, 1-based inclusive)"),
        sa.Column('strand', sa.String(1), nullable=False,
                  comment="DNA strand ('+' or '-')"),
        sa.Column('phase', sa.Integer,
                  comment="Reading frame phase (0, 1, or 2)"),
        sa.Column('transcript_id', UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(50), nullable=False,
                  comment="Data source"),
        sa.Column('extra_data', JSONB,
                  comment="Additional exon extra_data"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_exons_chromosome', 'exons', ['chromosome'])
    op.create_index('ix_exons_start', 'exons', ['start'])
    op.create_index('ix_exons_end', 'exons', ['end'])
    op.create_index('ix_exons_transcript_id', 'exons', ['transcript_id'])

    # 5. Create protein_domains table
    op.create_table(
        'protein_domains',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False,
                  comment="Domain name (e.g., 'POU-Specific Domain')"),
        sa.Column('short_name', sa.String(50),
                  comment="Short domain name (e.g., 'POU-S')"),
        sa.Column('start', sa.Integer, nullable=False,
                  comment="Domain start position (amino acid, 1-based)"),
        sa.Column('end', sa.Integer, nullable=False,
                  comment="Domain end position (amino acid, 1-based)"),
        sa.Column('length', sa.Integer, nullable=False,
                  comment="Domain length (amino acids)"),
        sa.Column('pfam_id', sa.String(50),
                  comment="Pfam identifier"),
        sa.Column('interpro_id', sa.String(50),
                  comment="InterPro identifier"),
        sa.Column('uniprot_id', sa.String(50),
                  comment="UniProt accession"),
        sa.Column('function', sa.Text,
                  comment="Domain function description"),
        sa.Column('transcript_id', UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(50), nullable=False,
                  comment="Data source (e.g., 'UniProt', 'Pfam', 'InterPro')"),
        sa.Column('evidence_code', sa.String(50),
                  comment="Evidence code (e.g., 'ECO:0000255')"),
        sa.Column('source_url', sa.Text,
                  comment="URL to domain annotation"),
        sa.Column('extra_data', JSONB,
                  comment="Additional domain extra_data"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_protein_domains_start', 'protein_domains', ['start'])
    op.create_index('ix_protein_domains_end', 'protein_domains', ['end'])
    op.create_index('ix_protein_domains_pfam_id', 'protein_domains', ['pfam_id'])
    op.create_index('ix_protein_domains_interpro_id', 'protein_domains', ['interpro_id'])
    op.create_index('ix_protein_domains_uniprot_id', 'protein_domains', ['uniprot_id'])
    op.create_index('ix_protein_domains_transcript_id', 'protein_domains', ['transcript_id'])


def downgrade() -> None:
    """Downgrade schema - drop reference genome tables."""
    op.drop_table('protein_domains')
    op.drop_table('exons')
    op.drop_table('transcripts')
    op.drop_table('genes')
    op.drop_table('reference_genomes')
