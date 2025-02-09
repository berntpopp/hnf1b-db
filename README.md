## 1. Schema Design Plan

### Collections and Their Purpose

- **Users**  
  This collection stores information about reviewers (the users who enter/review reports).  
  **Fields:**  
  - `_id` (MongoDB ObjectId)  
  - `user_id` (numeric ID from the sheet)  
  - `user_name`, `password`, `email`, `user_role`  
  - `first_name`, `family_name`, `orcid` (optional)

- **Individuals**  
  Each document represents an individual with HNF1B disease and contains basic demographic information.  
  **Fields:**  
  - `_id` (MongoDB ObjectId)  
  - `individual_id` (numeric identifier)  
  - `Sex`  
  - `age_reported` (or you could use separate fields for birth date, age at report, etc.)  
  - `cohort` (for example, “born” vs. “fetus”)  
  - *Relationships:* You might later add an array of report IDs (or simply reference reports by individual_id)

- **Reports**  
  Each report captures a clinical presentation submitted at a given time for an individual. There can be multiple reports per individual.  
  **Fields:**  
  - `_id` (MongoDB ObjectId)  
  - `report_id` (numeric)  
  - `individual_id` (reference to an Individual)  
  - `report_date` and `report_review_date`  
  - `reviewed_by` (user id reference, e.g. the reviewer who entered the report)  
  - `phenotypes`: an array of phenotype sub‑documents  
    - Each phenotype sub‑document might include a `phenotype_id`, a name, and additional attributes (for example, a “modifier” such as “unilateral”/“bilateral” and a flag to indicate if the phenotype is “described”)

- **Variants**  
  Although an individual may have multiple variant records over time, one variant is marked as current. Also, each variant record includes both classification and annotation data.  
  **Fields:**  
  - `_id` (MongoDB ObjectId)  
  - `variant_id` (numeric)  
  - `individual_id` (reference to an Individual)  
  - `is_current`: Boolean (indicates which variant is currently valid)  
  - **Classifications:**  
    - `verdict_classification`  
    - `criteria_classification`  
    - `comment_classification`  
    - `system_classification`  
    - `date_classification`  
  - **Annotations:**  
    - `variant_type` (e.g. SNV, CNV)  
    - `variant_reported`  
    - `ID` (an identifier from a variant database)  
    - `hg19_INFO`, `hg19`  
    - `hg38_INFO`, `hg38`  
    - `varsome`  
    - `detection_method` (note the corrected spelling)  
    - `segregation`

- **Publications**  
  This collection stores publication metadata (often pulled from PubMed).  
  **Fields:**  
  - `_id` (MongoDB ObjectId)  
  - `publication_id` (numeric)  
  - `publication_alias` (the alias from the sheets)  
  - `publication_type`  
  - `publication_entry_date`  
  - `PMID`, `DOI`  
  - `PDF`, and possibly a `PDF_drive_link`  
  - Other optional fields such as `title`, `abstract`, `journal`, etc.

### Data Modeling Decisions

- **Reference vs. Embedded Documents:**  
  In our design, we use separate collections for each domain. For example, reports refer to an individual by its identifier. This gives us flexibility (especially if the number of reports per individual is large).  
  For phenotypes in a report, if the number is moderate, we can embed them as sub‑documents within the report document.

- **Versioning of Variants:**  
  Since an individual may have several variant records (but only one is “current”), we store each variant in the Variants collection and add a Boolean field (e.g. `is_current`) to mark the current one.  
  Alternatively, you might embed an array of annotation/classification “versions” within a variant document. The proposed design here uses a flat collection with a flag.

- **Validation and Migration:**  
  Our import/migration script (written in Python) now validates and cleans data (using Pydantic models with custom validators) before inserting it into MongoDB. This same model is used by our API so that we maintain consistency between the imported data and the API’s expectations.

---

## 2. README Snippet (Schema Overview)

Below is a sample README section you could include in your repository to describe the database schema:

---

# HNF1B-db Database Schema

This database is designed to store clinical and genetic data for individuals with HNF1B disease. The data model is organized into several collections, each corresponding to a key domain of the application.

## Collections

### 1. **users**

Stores reviewer/user data.

**Document Example:**
```json
{
  "_id": "ObjectId(...)",
  "user_id": 1,
  "user_name": "johannes",
  "password": "hashedpassword",
  "email": "Johannes.Muench@medizin.uni-leipzig.de",
  "user_role": "Administrator",
  "first_name": "Johannes",
  "family_name": "Münch",
  "orcid": "0000-0003-1779-1876"
}
```

### 2. **individuals**

Stores basic demographic information for each individual with HNF1B disease.

**Document Example:**
```json
{
  "_id": "ObjectId(...)",
  "individual_id": 101,
  "Sex": "male",
  "individual_DOI": "optional external identifier"
}
```

### 3. **reports**

Stores clinical reports for individuals. An individual may have multiple reports over time. Each report records when it was entered/reviewed, by whom, and includes a list of phenotypes.

**Document Example:**
```json
{
  "_id": "ObjectId(...)",
  "report_id": 501,
  "individual_id": 101,
  "report_date": "2021-11-01T00:00:00Z",
  "report_review_date": "2021-11-05T00:00:00Z",
  "reviewed_by": 1,  // Reference to a user
  "phenotypes": [
    {
      "phenotype_id": "HP:0012622",
      "name": "Renal Insufficiency",
      "modifier": "severe",
      "described": true
    },
    {
      "phenotype_id": "HP:0100611",
      "name": "Kidney Biopsy",
      "modifier": null,
      "described": false
    }
  ]
}
```

### 4. **variants**

Stores genetic variant information for individuals. An individual may have several variant records over time, but one is marked as the current (or valid) variant. Each variant includes both annotation and classification data.

**Document Example:**
```json
{
  "_id": "ObjectId(...)",
  "variant_id": 3001,
  "individual_id": 101,
  "is_current": true,
  "classifications": {
    "verdict": "Pathogenic",
    "criteria": "1A, 2A, 3A, 4Cx6(0.9)",
    "comment": "Functional evidence provided",
    "system": "ACMG guidelines",
    "classification_date": "2022-06-06T00:00:00Z"
  },
  "annotations": {
    "variant_type": "Deletion",
    "variant_reported": "17q12 deletion",
    "ID": "dbVar:nssv1184554",
    "hg19_INFO": "IMPRECISE;SVTYPE=DEL;END=36192489",
    "hg19": "chr17-34815071-T-<DEL>",
    "hg38_INFO": "IMPRECISE;SVTYPE=DEL;END=37832869",
    "hg38": "chr17-36459258-T-<DEL>",
    "varsome": "HNF1B(NM_000458.4):c.406C>G (p.Gln136Glu)",
    "detection_method": "MLPA",
    "segregation": "de novo"
  }
}
```

### 5. **publications**

Stores publication metadata that may be linked to reports or used to extract phenotype data.

**Document Example:**
```json
{
  "_id": "ObjectId(...)",
  "publication_id": 19,
  "publication_alias": "pub018",
  "publication_type": "research",
  "publication_entry_date": "2021-11-01T00:00:00Z",
  "PMID": "15509593",
  "DOI": "10.1093/hmg/ddh338",
  "PDF": "barbacci2004.pdf",
  "PDF_drive_link": "https://drive.google.com/...",
  "Assigne": "JF",
  "IndividualsReviewed": 10,
  "Comment": null,
  "title": null,
  "abstract": null,
  "journal": null,
  "update_date": null
}
```

## Relationships Diagram

Below is a simplified diagram (using text/ASCII art) of the relationships between collections:

```
          +-----------+
          |   users   |
          +-----+-----+
                |
                | reviewed_by (user_id)
                v
        +---------------+
        |    reports    |<-----------------+
        +------+--------+                  |
               |                          |
               | individual_id            |
               v                          |
+------------------------+                |
|     individuals        |                |
+------------------------+                |
               ^                          |
               | (has one or more reports)|
               +--------------------------+
               
        +-------------------------+
        |       variants          |
        +-------------------------+
        | individual_id (ref)     |
        | is_current: Boolean     |
        | annotations/classifs    |
        +-------------------------+
        
        +-------------------------+
        |     publications        |
        +-------------------------+
        | publication_alias       |
        | PMID, DOI, etc.         |
        +-------------------------+
```

> **Note:** In the MongoDB design, relationships are maintained via reference fields (for example, the `individual_id` in reports and variants). You can choose to embed data (such as phenotypes in a report) if the number is small and you wish to optimize for read performance.  
>  
> The migration script (written in Python) now uses the same Pydantic models as the API, so that every record is validated and cleaned before insertion.
