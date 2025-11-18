"""Pydantic schemas for reference genome API responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class ReferenceGenomeSchema(BaseModel):
    """Reference genome assembly schema."""

    id: UUID
    name: str = Field(..., description="Assembly name (e.g., 'GRCh38', 'hg38')")
    ucsc_name: Optional[str] = Field(None, description="UCSC genome browser name")
    ensembl_name: Optional[str] = Field(None, description="Ensembl assembly name")
    ncbi_name: Optional[str] = Field(None, description="NCBI assembly accession")
    version: Optional[str] = Field(None, description="Assembly version/patch")
    release_date: Optional[datetime] = Field(None, description="Official release date")
    is_default: bool = Field(..., description="Whether this is the default assembly")
    source_url: Optional[str] = Field(None, description="URL to assembly information")
    extra_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional extra_data"
    )
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ExonSchema(BaseModel):
    """Exon schema."""

    id: UUID
    exon_number: int = Field(..., description="Exon number (1-based)")
    chromosome: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Exon start position (genomic, 1-based)")
    end: int = Field(..., description="Exon end position (genomic, 1-based)")
    strand: str = Field(..., description="DNA strand ('+' or '-')")
    phase: Optional[int] = Field(None, description="Reading frame phase (0, 1, or 2)")
    source: str = Field(..., description="Data source")
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ProteinDomainSchema(BaseModel):
    """Protein domain schema."""

    id: UUID
    name: str = Field(..., description="Domain name")
    short_name: Optional[str] = Field(None, description="Short domain name")
    start: int = Field(..., description="Domain start position (amino acid, 1-based)")
    end: int = Field(..., description="Domain end position (amino acid, 1-based)")
    length: int = Field(..., description="Domain length (amino acids)")
    pfam_id: Optional[str] = Field(None, description="Pfam identifier")
    interpro_id: Optional[str] = Field(None, description="InterPro identifier")
    uniprot_id: Optional[str] = Field(None, description="UniProt accession")
    function: Optional[str] = Field(None, description="Domain function description")
    source: str = Field(..., description="Data source")
    evidence_code: Optional[str] = Field(None, description="Evidence code")
    source_url: Optional[str] = Field(None, description="URL to domain annotation")
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class TranscriptSchema(BaseModel):
    """Transcript schema."""

    id: UUID
    transcript_id: str = Field(..., description="RefSeq or Ensembl transcript ID")
    protein_id: Optional[str] = Field(None, description="RefSeq protein ID")
    is_canonical: bool = Field(
        ..., description="Whether this is the canonical transcript"
    )
    cds_start: Optional[int] = Field(None, description="CDS start position (genomic)")
    cds_end: Optional[int] = Field(None, description="CDS end position (genomic)")
    exon_count: int = Field(..., description="Number of exons")
    source: str = Field(..., description="Data source")
    source_url: Optional[str] = Field(None, description="URL to transcript record")
    extra_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class TranscriptDetailSchema(TranscriptSchema):
    """Transcript schema with exons."""

    exons: List[ExonSchema] = Field(default_factory=list, description="Exon list")


class GeneSchema(BaseModel):
    """Gene schema."""

    id: UUID
    symbol: str = Field(..., description="Gene symbol")
    name: str = Field(..., description="Full gene name")
    chromosome: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Genomic start position (1-based)")
    end: int = Field(..., description="Genomic end position (1-based)")
    strand: str = Field(..., description="DNA strand ('+' or '-')")
    ensembl_id: Optional[str] = Field(None, description="Ensembl gene ID")
    ncbi_gene_id: Optional[str] = Field(None, description="NCBI Gene ID")
    hgnc_id: Optional[str] = Field(None, description="HGNC ID")
    omim_id: Optional[str] = Field(None, description="OMIM ID")
    source: str = Field(..., description="Data source")
    source_version: Optional[str] = Field(None, description="Source database version")
    source_url: Optional[str] = Field(None, description="URL to source record")
    extra_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class GeneDetailSchema(GeneSchema):
    """Gene schema with transcripts."""

    transcripts: List[TranscriptSchema] = Field(
        default_factory=list, description="Transcript isoforms"
    )


class GeneWithExonsSchema(GeneDetailSchema):
    """Gene schema with transcripts and exons."""

    transcripts: Sequence[TranscriptDetailSchema] = Field(  # type: ignore[assignment]
        default_factory=list, description="Transcript isoforms with exons"
    )


class ProteinDomainsResponse(BaseModel):
    """Response schema for protein domains endpoint."""

    gene: str = Field(..., description="Gene symbol")
    protein: Optional[str] = Field(None, description="RefSeq protein ID")
    uniprot: Optional[str] = Field(None, description="UniProt accession")
    length: Optional[int] = Field(None, description="Protein length (amino acids)")
    domains: List[ProteinDomainSchema] = Field(
        default_factory=list, description="Protein domains"
    )
    genome_build: str = Field(..., description="Genome assembly")
    updated_at: datetime = Field(..., description="Last update timestamp")


class GenomicRegionResponse(BaseModel):
    """Response schema for genomic region query."""

    region: str = Field(..., description="Genomic region (chr:start-end)")
    genome_build: str = Field(..., description="Genome assembly")
    genes: List[GeneSchema] = Field(default_factory=list, description="Genes in region")
    total: int = Field(..., description="Total number of genes")
