"""API integration modules for PubMed and Ensembl data enrichment."""

import calendar
from typing import Any, Dict

import requests
from Bio import Entrez

from .utils import parse_date


def get_pubmed_info(pmid: str) -> Dict[str, Any]:
    """Fetch publication information from PubMed API."""
    if not pmid:
        return {}

    try:
        handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
        records = Entrez.read(handle)
        handle.close()

        if "PubmedArticle" not in records or len(records["PubmedArticle"]) == 0:
            return {}

        article = records["PubmedArticle"][0]
        medline = article["MedlineCitation"]
        article_data = medline.get("Article", {})

        pmid_val = str(medline.get("PMID", ""))

        # Extract DOI
        doi = None
        if "ELocationID" in article_data:
            for eid in article_data["ELocationID"]:
                if eid.attributes.get("EIdType") == "doi":
                    doi = str(eid)
                    break

        # Extract title and abstract
        title = article_data.get("ArticleTitle", "")
        abstract = ""
        if "Abstract" in article_data:
            abstract_texts = article_data["Abstract"].get("AbstractText", [])
            if isinstance(abstract_texts, list):
                abstract = " ".join(abstract_texts)
            else:
                abstract = abstract_texts

        # Extract journal information
        journal = article_data.get("Journal", {})
        journal_title = journal.get("Title", "")
        journal_abbr = journal.get("ISOAbbreviation", "")

        # Extract publication date
        pub_date = journal.get("JournalIssue", {}).get("PubDate", {})
        year = pub_date.get("Year", "")
        raw_month = pub_date.get("Month", "01")
        day = pub_date.get("Day", "01")

        try:
            if raw_month.isalpha():
                month_num = list(calendar.month_abbr).index(raw_month.capitalize())
            else:
                month_num = int(raw_month)
        except Exception:
            month_num = 1

        pub_date_str = f"{year}-{month_num:02d}-{int(day):02d}" if year else ""
        publication_date = parse_date(pub_date_str)

        # Extract MeSH terms
        mesh_terms = []
        if "MeshHeadingList" in medline:
            for mesh in medline["MeshHeadingList"]:
                if "QualifierName" in mesh and mesh["QualifierName"]:
                    for qual in mesh["QualifierName"]:
                        mesh_terms.append(str(qual))
                elif "DescriptorName" in mesh:
                    mesh_terms.append(str(mesh["DescriptorName"]))

        # Extract chemicals
        chemicals = []
        if "ChemicalList" in medline:
            for chem in medline["ChemicalList"]:
                if "NameOfSubstance" in chem:
                    chemicals.append(str(chem["NameOfSubstance"]))

        # Extract supplemental MeSH
        suppl_mesh = []
        if "SupplMeshList" in medline:
            for s in medline["SupplMeshList"]:
                suppl_mesh.append(str(s))

        # Extract keywords
        keywords = []
        if "KeywordList" in medline:
            for klist in medline["KeywordList"]:
                keywords.extend(klist)

        all_keywords = keywords + mesh_terms + chemicals + suppl_mesh

        # Extract authors
        authors = []
        if "AuthorList" in article_data and len(article_data["AuthorList"]) > 0:
            for author in article_data["AuthorList"]:
                author_obj = {
                    "lastname": author.get("LastName", ""),
                    "firstname": author.get("ForeName", ""),
                    "initials": author.get("Initials", ""),
                    "affiliations": [],
                }
                if "AffiliationInfo" in author:
                    for aff in author["AffiliationInfo"]:
                        author_obj["affiliations"].append(
                            str(aff.get("Affiliation", "")).strip()
                        )
                authors.append(author_obj)

        return {
            "pmid": pmid_val,
            "doi": doi,
            "title": title,
            "abstract": abstract,
            "year": year,
            "month": raw_month,
            "day": day,
            "jabbrv": journal_abbr,
            "journal": journal_title,
            "keywords": all_keywords,
            "authors": authors,
            "publication_date": publication_date,
            "medical_specialty": [],
        }

    except Exception as e:
        print(f"Error retrieving PubMed info for PMID {pmid}: {e}")
        return {}


def update_publication_with_pubmed(pub: dict) -> dict:
    """Update publication data with information from PubMed API."""
    pmid = pub.get("PMID")
    if not pmid:
        return pub

    pubmed_info = get_pubmed_info(str(pmid))
    if pubmed_info:
        if not pub.get("title"):
            pub["title"] = pubmed_info.get("title", "")
        if not pub.get("abstract"):
            pub["abstract"] = pubmed_info.get("abstract", "")
        if not pub.get("publication_date") and pubmed_info.get("publication_date"):
            pub["publication_date"] = pubmed_info.get("publication_date")
        if not pub.get("journal_abbreviation"):
            pub["journal_abbreviation"] = pubmed_info.get("jabbrv", "")
        if not pub.get("journal"):
            pub["journal"] = pubmed_info.get("journal", "")
        if not pub.get("keywords"):
            pub["keywords"] = pubmed_info.get("keywords", [])
        pub["authors"] = pubmed_info.get("authors", [])
        if not pub.get("medical_specialty"):
            pub["medical_specialty"] = pubmed_info.get("medical_specialty", [])

    return pub


async def fetch_ensembl_gene_info(gene_symbol: str) -> Dict[str, Any]:
    """Fetch gene information from Ensembl REST API."""
    try:
        # Search for gene by symbol
        search_url = (
            f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene_symbol}"
        )
        headers = {"Content-Type": "application/json"}

        response = requests.get(search_url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(
                f"[fetch_ensembl_gene_info] Error fetching gene {gene_symbol}: {response.status_code}"
            )
            return {}

        gene_data = response.json()

        # Fetch additional protein domains if available
        gene_id = gene_data.get("id")
        if gene_id:
            protein_url = f"https://rest.ensembl.org/lookup/id/{gene_id}"
            protein_response = requests.get(protein_url, headers=headers, timeout=30)
            if protein_response.status_code == 200:
                protein_data = protein_response.json()
                gene_data.update(protein_data)

        return gene_data

    except Exception as e:
        print(
            f"[fetch_ensembl_gene_info] Error fetching Ensembl data for {gene_symbol}: {e}"
        )
        return {}


async def fetch_ensembl_protein_domains(protein_id: str) -> Dict[str, Any]:
    """Fetch protein domain information from Ensembl REST API."""
    try:
        domains_url = f"https://rest.ensembl.org/overlap/translation/{protein_id}"
        headers = {"Content-Type": "application/json"}

        response = requests.get(domains_url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(
                f"[fetch_ensembl_protein_domains] Error fetching domains for {protein_id}: {response.status_code}"
            )
            return {}

        domains_data = response.json()
        return {"domains": domains_data}

    except Exception as e:
        print(
            f"[fetch_ensembl_protein_domains] Error fetching protein domains for {protein_id}: {e}"
        )
        return {}


def sanitize_protein_value(val: Any) -> str:
    """Sanitize protein data values, handling NA/NaN cases."""
    s = str(val).strip() if val is not None else ""
    return "" if s.upper() in ("NA", "NAN") else s
