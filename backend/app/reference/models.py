"""Reference genome data models.

SQLAlchemy models for storing genomic reference data:
- Reference genomes (GRCh37, GRCh38, T2T-CHM13)
- Genes (HNF1B and chr17q12 region genes)
- Transcripts (RefSeq isoforms)
- Protein domains (UniProt/Pfam/InterPro)
- Exons (genomic coordinates)

Data sources:
- NCBI Gene: https://www.ncbi.nlm.nih.gov/gene
- Ensembl: https://www.ensembl.org
- UniProt: https://www.uniprot.org
- Pfam: http://pfam.xfam.org
- InterPro: https://www.ebi.ac.uk/interpro
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReferenceGenome(Base):
    """Reference genome assemblies (GRCh37, GRCh38, T2T-CHM13).

    Attributes:
        id: UUID primary key
        name: Assembly name (e.g., "GRCh38", "hg38")
        ucsc_name: UCSC genome browser name (e.g., "hg38", "hg19")
        ensembl_name: Ensembl assembly name (e.g., "GRCh38")
        ncbi_name: NCBI assembly name (e.g., "GCA_000001405.15")
        version: Assembly version/patch (e.g., "p14")
        release_date: Official release date
        is_default: Whether this is the default assembly for queries
        source_url: URL to assembly information
        extra_data: Additional assembly metadata (JSON)
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "reference_genomes"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core fields
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Assembly name (e.g., 'GRCh38', 'hg38')",
    )
    ucsc_name: Mapped[Optional[str]] = mapped_column(
        String(50), comment="UCSC genome browser name (e.g., 'hg38', 'hg19')"
    )
    ensembl_name: Mapped[Optional[str]] = mapped_column(
        String(50), comment="Ensembl assembly name"
    )
    ncbi_name: Mapped[Optional[str]] = mapped_column(
        String(100), comment="NCBI assembly accession (e.g., 'GCA_000001405.15')"
    )
    version: Mapped[Optional[str]] = mapped_column(
        String(20), comment="Assembly version/patch (e.g., 'p14')"
    )
    release_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), comment="Official release date"
    )
    is_default: Mapped[bool] = mapped_column(
        default=False,
        index=True,
        comment="Whether this is the default assembly for API queries",
    )

    # Provenance
    source_url: Mapped[Optional[str]] = mapped_column(
        Text, comment="URL to assembly information page"
    )
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Additional assembly metadata"
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    genes: Mapped[list["Gene"]] = relationship(
        "Gene", back_populates="genome", cascade="all, delete-orphan"
    )


class Gene(Base):
    """Gene reference data (symbol, name, coordinates).

    Attributes:
        id: UUID primary key
        symbol: Gene symbol (e.g., "HNF1B")
        name: Full gene name (e.g., "HNF1 homeobox B")
        chromosome: Chromosome (e.g., "17", "X", "MT")
        start: Genomic start position (1-based, inclusive)
        end: Genomic end position (1-based, inclusive)
        strand: DNA strand ('+' or '-')
        genome_id: Foreign key to reference_genomes
        ensembl_id: Ensembl gene ID (e.g., "ENSG00000275410")
        ncbi_gene_id: NCBI Gene ID (e.g., "6928")
        hgnc_id: HGNC ID (e.g., "HGNC:11630")
        omim_id: OMIM ID (e.g., "189907")
        source: Data source (e.g., "NCBI Gene", "Ensembl")
        source_version: Source database version
        source_url: URL to source record
        extra_data: Additional gene metadata (JSON)
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "genes"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core fields
    symbol: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="Gene symbol (e.g., 'HNF1B')"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Full gene name"
    )
    chromosome: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Chromosome (e.g., '17', 'X', 'MT')",
    )
    start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Genomic start position (1-based, inclusive)",
    )
    end: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Genomic end position (1-based, inclusive)",
    )
    strand: Mapped[str] = mapped_column(
        String(1), nullable=False, comment="DNA strand ('+' or '-')"
    )

    # Foreign key
    genome_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference_genomes.id"),
        nullable=False,
        index=True,
    )

    # External identifiers
    ensembl_id: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, comment="Ensembl gene ID"
    )
    ncbi_gene_id: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, comment="NCBI Gene ID"
    )
    hgnc_id: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, comment="HGNC ID"
    )
    omim_id: Mapped[Optional[str]] = mapped_column(String(50), comment="OMIM ID")

    # Provenance
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Data source (e.g., 'NCBI Gene', 'Ensembl')"
    )
    source_version: Mapped[Optional[str]] = mapped_column(
        String(50), comment="Source database version"
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        Text, comment="URL to source record"
    )
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Additional gene metadata"
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    genome: Mapped["ReferenceGenome"] = relationship(
        "ReferenceGenome", back_populates="genes"
    )
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript", back_populates="gene", cascade="all, delete-orphan"
    )


class Transcript(Base):
    """Transcript isoforms (RefSeq, Ensembl).

    Attributes:
        id: UUID primary key
        transcript_id: RefSeq or Ensembl transcript ID (e.g., "NM_000458.4")
        gene_id: Foreign key to genes
        protein_id: RefSeq protein ID (e.g., "NP_000449.3")
        is_canonical: Whether this is the canonical transcript
        cds_start: CDS start position (genomic coordinates)
        cds_end: CDS end position (genomic coordinates)
        exon_count: Number of exons
        source: Data source (e.g., "RefSeq", "Ensembl")
        source_url: URL to transcript record
        extra_data: Additional transcript metadata (JSON)
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "transcripts"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core fields
    transcript_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="RefSeq or Ensembl transcript ID",
    )
    protein_id: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, comment="RefSeq protein ID (e.g., 'NP_000449.3')"
    )
    is_canonical: Mapped[bool] = mapped_column(
        default=False, index=True, comment="Whether this is the canonical transcript"
    )
    cds_start: Mapped[Optional[int]] = mapped_column(
        Integer, comment="CDS start position (genomic coordinates)"
    )
    cds_end: Mapped[Optional[int]] = mapped_column(
        Integer, comment="CDS end position (genomic coordinates)"
    )
    exon_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Number of exons"
    )

    # Foreign key
    gene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("genes.id"), nullable=False, index=True
    )

    # Provenance
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Data source (e.g., 'RefSeq', 'Ensembl')"
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        Text, comment="URL to transcript record"
    )
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Additional transcript metadata"
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    gene: Mapped["Gene"] = relationship("Gene", back_populates="transcripts")
    exons: Mapped[list["Exon"]] = relationship(
        "Exon", back_populates="transcript", cascade="all, delete-orphan"
    )
    protein_domains: Mapped[list["ProteinDomain"]] = relationship(
        "ProteinDomain", back_populates="transcript", cascade="all, delete-orphan"
    )


class Exon(Base):
    """Exon genomic coordinates.

    Attributes:
        id: UUID primary key
        exon_number: Exon number (1-based)
        transcript_id: Foreign key to transcripts
        chromosome: Chromosome (denormalized from gene)
        start: Exon start position (genomic coordinates, 1-based inclusive)
        end: Exon end position (genomic coordinates, 1-based inclusive)
        strand: DNA strand (denormalized from gene)
        phase: Reading frame phase (0, 1, or 2)
        source: Data source
        extra_data: Additional exon metadata (JSON)
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "exons"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core fields
    exon_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Exon number (1-based)"
    )
    chromosome: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Chromosome (denormalized from gene)",
    )
    start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Exon start position (genomic, 1-based inclusive)",
    )
    end: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Exon end position (genomic, 1-based inclusive)",
    )
    strand: Mapped[str] = mapped_column(
        String(1), nullable=False, comment="DNA strand ('+' or '-')"
    )
    phase: Mapped[Optional[int]] = mapped_column(
        Integer, comment="Reading frame phase (0, 1, or 2)"
    )

    # Foreign key
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transcripts.id"), nullable=False, index=True
    )

    # Provenance
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Data source"
    )
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Additional exon metadata"
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    transcript: Mapped["Transcript"] = relationship(
        "Transcript", back_populates="exons"
    )


class ProteinDomain(Base):
    """Protein domain annotations (UniProt/Pfam/InterPro).

    Attributes:
        id: UUID primary key
        transcript_id: Foreign key to transcripts
        name: Domain name (e.g., "POU-Specific Domain")
        short_name: Short domain name (e.g., "POU-S")
        start: Domain start position (amino acid, 1-based)
        end: Domain end position (amino acid, 1-based)
        length: Domain length (amino acids)
        pfam_id: Pfam identifier (e.g., "PF00157")
        interpro_id: InterPro identifier (e.g., "IPR000327")
        uniprot_id: UniProt accession (e.g., "P35680")
        function: Domain function description
        source: Data source (e.g., "UniProt", "Pfam", "InterPro")
        evidence_code: Evidence code (e.g., "ECO:0000255")
        source_url: URL to domain annotation
        extra_data: Additional domain metadata (JSON)
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "protein_domains"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core fields
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Domain name (e.g., 'POU-Specific Domain')"
    )
    short_name: Mapped[Optional[str]] = mapped_column(
        String(50), comment="Short domain name (e.g., 'POU-S')"
    )
    start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Domain start position (amino acid, 1-based)",
    )
    end: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Domain end position (amino acid, 1-based)",
    )
    length: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Domain length (amino acids)"
    )

    # External identifiers
    pfam_id: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, comment="Pfam identifier"
    )
    interpro_id: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, comment="InterPro identifier"
    )
    uniprot_id: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, comment="UniProt accession"
    )

    # Annotations
    function: Mapped[Optional[str]] = mapped_column(
        Text, comment="Domain function description"
    )

    # Foreign key
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transcripts.id"), nullable=False, index=True
    )

    # Provenance
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Data source (e.g., 'UniProt', 'Pfam', 'InterPro')",
    )
    evidence_code: Mapped[Optional[str]] = mapped_column(
        String(50), comment="Evidence code (e.g., 'ECO:0000255')"
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        Text, comment="URL to domain annotation"
    )
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Additional domain metadata"
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    transcript: Mapped["Transcript"] = relationship(
        "Transcript", back_populates="protein_domains"
    )
