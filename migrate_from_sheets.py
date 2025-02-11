# File: migrate_from_sheets.py
import asyncio
import math
import re
import pandas as pd
from app.database import db
from app.config import settings
from app.models import User, Individual, Publication, Report, Variant

# NEW: Import Entrez from BioPython for PubMed queries.
from Bio import Entrez
Entrez.email = "your_email@example.com"  # Replace with your actual email address

SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"

# GIDs for each sheet:
GID_REVIEWERS = "1321366018"      # Reviewers sheet
GID_INDIVIDUALS = "0"             # Individuals sheet (contains both individual and report data)
GID_PUBLICATIONS = "1670256162"   # Publications sheet

# GIDs for additional mapping sheets:
PHENOTYPE_GID = "1119329208"       # Phenotype sheet
MODIFIER_GID   = "1741928801"      # Modifier sheet

# ---------------------------------------------------
def none_if_nan(v):
    if pd.isna(v):
        return None
    if isinstance(v, str) and v.strip().upper() == "NA":
        return None
    return v

# ---------------------------------------------------
def parse_date(value):
    """Convert a date-like value to a Python datetime object using Pandas."""
    try:
        if value is None:
            return None
        dt = pd.to_datetime(value, errors='coerce')
        if pd.isnull(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None

# ---------------------------------------------------
def csv_url(spreadsheet_id: str, gid: str) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    print(f"[csv_url] Built URL: {url}")
    return url

# ---------------------------------------------------
def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from DataFrame column names."""
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    return df

# ---------------------------------------------------
async def load_phenotype_mappings():
    url = csv_url(SPREADSHEET_ID, PHENOTYPE_GID)
    df = pd.read_csv(url)
    df = normalize_dataframe_columns(df)
    mapping = {}
    for idx, row in df.iterrows():
        key = str(row["phenotype_category"]).strip().lower()
        mapping[key] = {
            "phenotype_id": row["phenotype_id"],
            "name": row["phenotype_name"]
        }
    print(f"[load_phenotype_mappings] Loaded mapping for {len(mapping)} phenotype categories.")
    return mapping

# ---------------------------------------------------
async def load_modifier_mappings():
    url = csv_url(SPREADSHEET_ID, MODIFIER_GID)
    df = pd.read_csv(url)
    df = normalize_dataframe_columns(df)
    mapping = {}
    for idx, row in df.iterrows():
        key = str(row["modifier_name"]).strip().lower()
        mapping[key] = {
            "modifier_id": row["modifier_id"],
            "name": row["modifier_name"].strip(),
            "description": row.get("modifier_description", "").strip(),
            "synonyms": row.get("modifier_synonyms", "").strip()
        }
        if pd.notna(row.get("modifier_synonyms")):
            synonyms = row["modifier_synonyms"].split(",")
            for syn in synonyms:
                mapping[syn.strip().lower()] = {
                    "modifier_id": row["modifier_id"],
                    "name": row["modifier_name"].strip(),
                    "description": row.get("modifier_description", "").strip(),
                    "synonyms": row.get("modifier_synonyms", "").strip()
                }
    print(f"[load_modifier_mappings] Loaded mapping for {len(mapping)} modifier keys.")
    return mapping

# ---------------------------------------------------
def get_pubmed_info(pmid: str) -> dict:
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
        doi = None
        if "ELocationID" in article_data:
            for eid in article_data["ELocationID"]:
                if eid.attributes.get("EIdType") == "doi":
                    doi = str(eid)
                    break
        title = article_data.get("ArticleTitle", "")
        abstract = ""
        if "Abstract" in article_data:
            abstract_texts = article_data["Abstract"].get("AbstractText", [])
            if isinstance(abstract_texts, list):
                abstract = " ".join(abstract_texts)
            else:
                abstract = abstract_texts
        journal = article_data.get("Journal", {})
        journal_title = journal.get("Title", "")
        journal_abbr = journal.get("ISOAbbreviation", "")
        pub_date = journal.get("JournalIssue", {}).get("PubDate", {})
        year = pub_date.get("Year", "")
        raw_month = pub_date.get("Month", "01")
        day = pub_date.get("Day", "01")
        import calendar
        try:
            if raw_month.isalpha():
                month_num = list(calendar.month_abbr).index(raw_month.capitalize())
            else:
                month_num = int(raw_month)
        except Exception:
            month_num = 1
        publication_date = f"{year}-{month_num:02d}-{int(day):02d}" if year else ""
        # --- Extract MeSH terms and chemicals ---
        mesh_terms = []
        if "MeshHeadingList" in medline:
            for mesh in medline["MeshHeadingList"]:
                if "QualifierName" in mesh and mesh["QualifierName"]:
                    for qual in mesh["QualifierName"]:
                        mesh_terms.append(str(qual))
                elif "DescriptorName" in mesh:
                    mesh_terms.append(str(mesh["DescriptorName"]))
        chemicals = []
        if "ChemicalList" in medline:
            for chem in medline["ChemicalList"]:
                if "NameOfSubstance" in chem:
                    chemicals.append(str(chem["NameOfSubstance"]))
        suppl_mesh = []
        if "SupplMeshList" in medline:
            for s in medline["SupplMeshList"]:
                suppl_mesh.append(str(s))
        keywords = []
        if "KeywordList" in medline:
            for klist in medline["KeywordList"]:
                keywords.extend(klist)
        # Return keywords as a list (do not join into a single string)
        all_keywords = keywords + mesh_terms + chemicals + suppl_mesh
        # --- Build authors list ---
        authors = []
        if "AuthorList" in article_data and len(article_data["AuthorList"]) > 0:
            for author in article_data["AuthorList"]:
                author_obj = {
                    "lastname": author.get("LastName", ""),
                    "firstname": author.get("ForeName", ""),
                    "initials": author.get("Initials", ""),
                    "affiliations": []
                }
                if "AffiliationInfo" in author:
                    for aff in author["AffiliationInfo"]:
                        author_obj["affiliations"].append(str(aff.get("Affiliation", "")).strip())
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
            "keywords": all_keywords,  # Return as a list
            "authors": authors,
            "publication_date": publication_date,
            "medical_specialty": []  # Currently empty; adjust if needed.
        }
    except Exception as e:
        print(f"Error retrieving PubMed info for PMID {pmid}: {e}")
        return {}

# ---------------------------------------------------
def update_publication_with_pubmed(pub: dict) -> dict:
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

# ---------------------------------------------------
async def import_users():
    print("[import_users] Starting import of reviewers/users.")
    url = csv_url(SPREADSHEET_ID, GID_REVIEWERS)
    reviewers_df = pd.read_csv(url)
    reviewers_df = reviewers_df.dropna(how="all")
    reviewers_df = normalize_dataframe_columns(reviewers_df)
    expected_columns = ['user_id', 'user_name', 'password', 'email',
                        'user_role', 'first_name', 'family_name', 'orcid', 'abbreviation']
    missing = [col for col in expected_columns if col not in reviewers_df.columns]
    if missing:
        raise KeyError(f"[import_users] Missing expected columns in Reviewers sheet: {missing}")
    users_df = reviewers_df[expected_columns].sort_values('user_id')
    validated_users = []
    for idx, row in users_df.iterrows():
        try:
            user = User(**row)
            validated_users.append(user.model_dump(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_users] Validation error in row {idx}: {e}")
    print(f"[import_users] Inserting {len(validated_users)} valid users into database...")
    await db.users.delete_many({})
    if validated_users:
        await db.users.insert_many(validated_users)
    print(f"[import_users] Imported {len(validated_users)} users.")

# ---------------------------------------------------
async def import_publications():
    print("[import_publications] Starting import of publications.")
    url = csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
    publications_df = pd.read_csv(url)
    publications_df = publications_df.dropna(how="all")
    publications_df = normalize_dataframe_columns(publications_df)
    # Normalize the comment column: rename "Comment" (from the sheet) to "comment"
    if "Comment" in publications_df.columns:
        publications_df.rename(columns={"Comment": "comment"}, inplace=True)
    # Convert NaN in the comment column to None
    if "comment" in publications_df.columns:
        publications_df["comment"] = publications_df["comment"].apply(none_if_nan)
    # Convert keywords column (if present) into a list of strings.
    if "keywords" in publications_df.columns:
        publications_df["keywords"] = publications_df["keywords"].apply(lambda x: [s.strip() for s in x.split(",")] if isinstance(x, str) else [])
    # Convert medical_specialty column (if present) into a list of strings.
    if "medical_specialty" in publications_df.columns:
        publications_df["medical_specialty"] = publications_df["medical_specialty"].apply(lambda x: [s.strip() for s in x.split(",")] if isinstance(x, str) else [])
    # --- Build reviewer mapping using the "Assigne" column.
    # We now match the value in the "Assigne" column to the "abbreviation" field in the users collection.
    user_docs = await db.users.find({}, {"abbreviation": 1}).to_list(length=None)
    reviewer_mapping = {}
    for user_doc in user_docs:
        # Use the value in the "abbreviation" field as the key (lowercased)
        key = user_doc["abbreviation"].strip().lower()
        reviewer_mapping[key] = user_doc["_id"]
    print(f"[import_publications] Reviewer mapping: {reviewer_mapping}")
    validated_publications = []
    for idx, row in publications_df.iterrows():
        try:
            if "Assigne" in row:
                assigne_val = row["Assigne"]
                if pd.notna(assigne_val):
                    row["assignee"] = reviewer_mapping.get(assigne_val.strip().lower())
                else:
                    row["assignee"] = None
                row = row.drop(labels=["Assigne"])
            pub = Publication(**row)
            pub_dict = pub.model_dump(by_alias=True, exclude_none=True)
            # NEW: Update publication with PubMed info if PMID is provided and title is empty.
            if pub_dict.get("PMID") and not pub_dict.get("title"):
                pub_dict = update_publication_with_pubmed(pub_dict)
            validated_publications.append(pub_dict)
        except Exception as e:
            print(f"[import_publications] Validation error in row {idx}: {e}")
    print(f"[import_publications] Inserting {len(validated_publications)} valid publications into database...")
    await db.publications.delete_many({})
    if validated_publications:
        await db.publications.insert_many(validated_publications)
    print(f"[import_publications] Imported {len(validated_publications)} publications.")

# ---------------------------------------------------
async def import_individuals_with_reports():
    print("[import_individuals] Starting import of individuals with embedded reports.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)
    print(f"[import_individuals] Normalized columns: {df.columns.tolist()}")
    base_cols = ['individual_id', 'DupCheck', 'IndividualIdentifier', 'Problematic', 'Cohort', 'Sex', 'AgeOnset', 'AgeReported']
    if "Publication" in df.columns:
        base_cols.append("Publication")
    if "ReviewDate" in df.columns:
        base_cols.append("ReviewDate")
    if "Comment" in df.columns:
        base_cols.append("Comment")
    pub_docs = await db.publications.find({}, {"publication_alias": 1}).to_list(length=None)
    publication_mapping = {
        doc["publication_alias"].strip().lower(): doc["_id"]
        for doc in pub_docs if "publication_alias" in doc
    }
    print(f"[import_individuals] Loaded publication mapping for {len(publication_mapping)} publications.")
    user_docs = await db.users.find({}, {"email": 1}).to_list(length=None)
    user_mapping = {}
    for user_doc in user_docs:
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["_id"]
    phenotype_cols = [
        'RenalInsufficancy', 'Hyperechogenicity', 'RenalCysts', 'MulticysticDysplasticKidney',
        'KidneyBiopsy', 'RenalHypoplasia', 'SolitaryKidney', 'UrinaryTractMalformation',
        'GenitalTractAbnormality', 'AntenatalRenalAbnormalities', 'Hypomagnesemia',
        'Hypokalemia', 'Hyperuricemia', 'Gout', 'MODY', 'PancreaticHypoplasia',
        'ExocrinePancreaticInsufficiency', 'Hyperparathyroidism', 'NeurodevelopmentalDisorder',
        'MentalDisease', 'Seizures', 'BrainAbnormality', 'PrematureBirth',
        'CongenitalCardiacAnomalies', 'EyeAbnormality', 'ShortStature',
        'MusculoskeletalFeatures', 'DysmorphicFeatures', 'ElevatedHepaticTransaminase',
        'AbnormalLiverPhysiology'
    ]
    phenotype_mapping = await load_phenotype_mappings()
    modifier_mapping = await load_modifier_mappings()
    grouped = df.groupby('individual_id')
    validated_individuals = []
    for indiv_id, group in grouped:
        base_data = group.iloc[0][base_cols].to_dict()
        base_publication_alias = base_data.pop('Publication', None)
        base_review_date = base_data.pop('ReviewDate', None)
        base_comment = base_data.pop('Comment', None)
        reports = []
        for idx, row in group.iterrows():
            if pd.notna(row.get('report_id')):
                report_data = {'report_id': row['report_id']}
                review_by_email = row.get('ReviewBy')
                if pd.notna(review_by_email):
                    report_data['reviewed_by'] = user_mapping.get(review_by_email.strip().lower())
                else:
                    report_data['reviewed_by'] = None
                phenotypes_obj = {}
                for col in phenotype_cols:
                    raw_val = row.get(col, "")
                    reported_val = str(raw_val).strip() if pd.notna(raw_val) else ""
                    pheno_key = col.strip().lower()
                    std_info = phenotype_mapping.get(pheno_key, {"phenotype_id": col, "name": col})
                    lower_val = reported_val.lower()
                    if lower_val in ["yes", "no", "not reported"]:
                        described = lower_val
                        modifier_obj = None
                    else:
                        described = "yes"
                        manual_modifier_map = {
                            "unilateral left": "left",
                            "unilateral right": "right",
                            "unilateral unspecified": "unilateral",
                            "bilateral": "bilateral"
                        }
                        if pheno_key in ["congenitalcardiacanomalies", "antenatalrenalabnormalities"]:
                            modifier_key = "congenital onset"
                        else:
                            modifier_key = manual_modifier_map.get(lower_val, lower_val)
                        modifier_obj = modifier_mapping.get(modifier_key)
                    phenotypes_obj[std_info["phenotype_id"]] = {
                        "phenotype_id": std_info["phenotype_id"],
                        "name": std_info["name"],
                        "modifier": modifier_obj,
                        "described": described
                    }
                report_data['phenotypes'] = phenotypes_obj
                pub_alias = row.get('Publication')
                if not pd.notna(pub_alias) and base_publication_alias:
                    pub_alias = base_publication_alias
                if pd.notna(pub_alias):
                    pub_alias_lower = str(pub_alias).strip().lower()
                    pub_obj_id = publication_mapping.get(pub_alias_lower)
                    if pub_obj_id:
                        report_data["publication_ref"] = pub_obj_id
                    else:
                        print(f"[import_individuals] Warning: Publication alias '{pub_alias}' not found for individual {indiv_id}.")
                review_date_val = parse_date(row.get('ReviewDate')) or parse_date(base_review_date)
                if review_date_val is not None:
                    report_data["review_date"] = review_date_val
                comment_val = row.get('Comment') or base_comment
                if pd.notna(comment_val):
                    report_data["comment"] = str(comment_val).strip()
                else:
                    report_data["comment"] = ""
                reports.append(report_data)
        base_data['reports'] = reports
        try:
            indiv = Individual(**base_data)
            validated_individuals.append(indiv.model_dump(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_individuals] Validation error for individual {indiv_id}: {e}")
    print(f"[import_individuals] Inserting {len(validated_individuals)} valid individuals with embedded reports into database...")
    await db.individuals.delete_many({})
    if validated_individuals:
        await db.individuals.insert_many(validated_individuals)
    print(f"[import_individuals] Imported {len(validated_individuals)} individuals with embedded reports.")

# ---------------------------------------------------
async def import_variants():
    print("[import_variants] Starting import of variants.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)
    print(f"[import_variants] Normalized columns: {df.columns.tolist()}")

    # Build unique key using these columns (do not include VariantReported or Varsome)
    variant_key_cols = ['VariantType', 'ID', 'hg19_INFO', 'hg19', 'hg38_INFO', 'hg38']
    unique_variants = {}
    individual_variant_info = {}

    # Classification columns to be extracted.
    classification_cols = [
        'verdict_classification', 'criteria_classification',
        'comment_classification', 'system_classification', 'date_classification'
    ]

    # Build publication mapping for linking publications via Publication column.
    pub_docs = await db.publications.find({}, {"publication_alias": 1}).to_list(length=None)
    publication_mapping = {
         doc["publication_alias"].strip().lower(): doc["_id"]
         for doc in pub_docs if "publication_alias" in doc
    }

    for idx, row in df.iterrows():
        if pd.notna(row.get('VariantType')):
            key_parts = []
            for col in variant_key_cols:
                val = none_if_nan(row.get(col))
                key_parts.append(str(val).strip() if val is not None else "")
            variant_key = "|".join(key_parts)
            sp_indiv_id = row['individual_id']
            det_method = none_if_nan(row.get('DetecionMethod') or row.get('DetectionMethod'))
            seg = none_if_nan(row.get('Segregation'))
            individual_variant_info[sp_indiv_id] = {
                "detection_method": det_method,
                "segregation": seg
            }
            # Extract classification data.
            classification = {}
            if any(col in row and pd.notna(row.get(col)) for col in classification_cols):
                classification = {
                    'verdict': none_if_nan(row.get('verdict_classification')),
                    'criteria': none_if_nan(row.get('criteria_classification')),
                    'comment': none_if_nan(row.get('comment_classification')),
                    'system': none_if_nan(row.get('system_classification')),
                    'classification_date': parse_date(row.get('date_classification'))
                }
            # Build variant_data without VariantReported and Varsome.
            variant_data = {
                'variant_type': row.get('VariantType'),
                'ID': none_if_nan(row.get('ID')),
                'hg19_INFO': none_if_nan(row.get('hg19_INFO')),
                'hg19': none_if_nan(row.get('hg19')),
                'hg38_INFO': none_if_nan(row.get('hg38_INFO')),
                'hg38': none_if_nan(row.get('hg38'))
            }
            # Build annotation from the Varsome column.
            annotation = {}
            varsome_val = none_if_nan(row.get('Varsome'))
            if pd.notna(varsome_val):
                varsome_str = str(varsome_val)
                pattern = r"^[^(]+\(([^)]+)\):([^ ]+)\s+(\(p\..+\))"
                m = re.match(pattern, varsome_str)
                if m:
                    transcript = m.group(1)
                    c_dot = m.group(2)
                    p_dot = m.group(3)
                else:
                    transcript = varsome_str
                    c_dot = None
                    p_dot = None
                annotation = {
                    "transcript": transcript,
                    "c_dot": c_dot,
                    "p_dot": p_dot,
                    "source": "varsome",
                    "annotation_date": parse_date(row.get('date_classification'))
                }
            # Build reported entry from VariantReported and Publication columns.
            reported_entry = {}
            vr = none_if_nan(row.get('VariantReported'))
            if vr:
                reported_entry["variant_reported"] = vr
                pub_val = none_if_nan(row.get('Publication'))
                if pub_val:
                    pub_obj_id = publication_mapping.get(str(pub_val).strip().lower())
                    reported_entry["publication_ref"] = pub_obj_id
                else:
                    reported_entry["publication_ref"] = None

            # Update unique_variants.
            if variant_key in unique_variants:
                if sp_indiv_id not in unique_variants[variant_key]['individual_ids']:
                    unique_variants[variant_key]['individual_ids'].append(sp_indiv_id)
                if reported_entry and "variant_reported" in reported_entry:
                    rep_arr = unique_variants[variant_key].setdefault("reported", [])
                    if reported_entry not in rep_arr:
                        rep_arr.append(reported_entry)
                if annotation and any(annotation.values()):
                    ann_arr = unique_variants[variant_key].setdefault("annotations", [])
                    if annotation not in ann_arr:
                        ann_arr.append(annotation)
                if classification and any(classification.values()):
                    cls_arr = unique_variants[variant_key].setdefault("classifications", [])
                    if classification not in cls_arr:
                        cls_arr.append(classification)
            else:
                unique_variants[variant_key] = {
                    "variant_data": variant_data,
                    "individual_ids": [sp_indiv_id],
                    "reported": [reported_entry] if reported_entry and "variant_reported" in reported_entry else [],
                    "annotations": [annotation] if annotation and any(annotation.values()) else [],
                    "classifications": [classification] if classification and any(classification.values()) else []
                }
    print(f"[import_variants] Found {len(unique_variants)} unique variants.")

    spid_to_objid = {}
    async for doc in db.individuals.find({}, {"individual_id": 1}):
        spid = doc.get("individual_id")
        if spid is not None:
            spid_to_objid[spid] = doc["_id"]

    variant_docs_to_insert = []
    variant_id_counter = 1
    for key, info in unique_variants.items():
        variant_doc = info["variant_data"]
        variant_doc['variant_id'] = variant_id_counter
        objid_list = []
        for spid in info["individual_ids"]:
            if spid in spid_to_objid:
                objid_list.append(spid_to_objid[spid])
        variant_doc['individual_ids'] = objid_list
        variant_doc['classifications'] = info.get('classifications', [])
        variant_doc['annotations'] = info.get('annotations', [])
        variant_doc['reported'] = info.get('reported', [])
        variant_docs_to_insert.append(variant_doc)
        variant_id_counter += 1

    print(f"[import_variants] Inserting {len(variant_docs_to_insert)} unique variants into database...")
    await db.variants.delete_many({})
    inserted_result = await db.variants.insert_many(variant_docs_to_insert)
    inserted_ids = inserted_result.inserted_ids
    variant_key_to_objid = {}
    for i, key in enumerate(unique_variants.keys()):
        variant_key_to_objid[key] = inserted_ids[i]
    print(f"[import_variants] Inserted {len(variant_docs_to_insert)} unique variants into database.")

    print("[import_variants] Updating individuals with variant references...")
    async for indiv_doc in db.individuals.find({}):
        sp_indiv_id = indiv_doc.get("individual_id")
        found_variant_objid = None
        for key, info in unique_variants.items():
            if sp_indiv_id in info["individual_ids"]:
                found_variant_objid = variant_key_to_objid.get(key)
                break
        if found_variant_objid is not None:
            det_seg = individual_variant_info.get(sp_indiv_id, {})
            variant_ref = {
                "variant_ref": found_variant_objid,
                "detection_method": det_seg.get("detection_method"),
                "segregation": det_seg.get("segregation")
            }
            await db.individuals.update_one(
                {"_id": indiv_doc["_id"]},
                {"$set": {"variant": variant_ref}}
            )
    print("[import_variants] Updated individuals with variant references.")

# ---------------------------------------------------
async def main():
    print("[main] Starting migration process...")
    try:
        await import_users()
    except Exception as e:
        print(f"[main] Error during import_users: {e}")
    try:
        await import_publications()
    except Exception as e:
        print(f"[main] Error during import_publications: {e}")
    try:
        await import_individuals_with_reports()
    except Exception as e:
        print(f"[main] Error during import_individuals_with_reports: {e}")
    try:
        await import_variants()
    except Exception as e:
        print(f"[main] Error during import_variants: {e}")
    print("[main] Migration process complete.")

if __name__ == "__main__":
    asyncio.run(main())
