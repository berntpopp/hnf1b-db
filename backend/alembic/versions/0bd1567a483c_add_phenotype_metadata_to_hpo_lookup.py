"""add_phenotype_metadata_to_hpo_lookup

Revision ID: 0bd1567a483c
Revises: b1e70338f190
Create Date: 2025-11-14 22:31:40.906668

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0bd1567a483c'
down_revision: Union[str, Sequence[str], None] = 'b1e70338f190'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add phenotype metadata columns to hpo_terms_lookup table.

    Adds columns from the Google Sheets phenotypes table:
    - category: Original column name (e.g., "RenalCysts", "Hypomagnesemia")
    - description: Detailed medical description
    - synonyms: Alternative terms
    - recommendation: "required" or "recommended"
    - group: Clinical grouping (Kidney, Hormones, Brain, etc.)
    """
    # Add new columns
    op.execute("""
        ALTER TABLE hpo_terms_lookup
        ADD COLUMN IF NOT EXISTS category VARCHAR(100),
        ADD COLUMN IF NOT EXISTS description TEXT,
        ADD COLUMN IF NOT EXISTS synonyms TEXT,
        ADD COLUMN IF NOT EXISTS recommendation VARCHAR(20),
        ADD COLUMN IF NOT EXISTS "group" VARCHAR(50)
    """)

    # Truncate and repopulate with full metadata from Google Sheets phenotypes table
    op.execute("TRUNCATE TABLE hpo_terms_lookup")

    # Insert all phenotype terms with complete metadata
    # Data source: Google Sheets "phenotypes" tab
    op.execute("""
        INSERT INTO hpo_terms_lookup (hpo_id, label, category, description, synonyms, recommendation, "group", phenopacket_count) VALUES
        -- Kidney phenotypes
        ('HP:0012622', 'chronic kidney disease, not specified', 'RenalInsufficancy',
         'Functional anomaly of the kidney persisting for at least three months.',
         'Progressive renal insufficiency, Loss of renal function, Renal insufficiency, progressive, Chronic kidney disease, Renal failure, progressive, Progressive renal failure',
         'required', 'Kidney', 0),
        ('HP:0012623', 'Stage 1 chronic kidney disease', 'RenalInsufficancy',
         'A type of chronic kidney disease with normal or increased glomerular filtration rate (GFR at least 90 mL/min/1.73 m2).',
         'No synonyms found for this term.',
         'required', 'Kidney', 0),
        ('HP:0012624', 'Stage 2 chronic kidney disease', 'RenalInsufficancy',
         'A type of chronic kidney disease with mildly reduced glomerular filtration rate (GFR 60-89 mL/min/1.73 m2).',
         'No synonyms found for this term.',
         'required', 'Kidney', 0),
        ('HP:0012625', 'Stage 3 chronic kidney disease', 'RenalInsufficancy',
         'A type of chronic kidney disease with moderately reduced glomerular filtration rate (GFR 30-59 mL/min/1.73 m2).',
         'No synonyms found for this term.',
         'required', 'Kidney', 0),
        ('HP:0012626', 'Stage 4 chronic kidney disease', 'RenalInsufficancy',
         'A type of chronic kidney disease with severely reduced glomerular filtration rate (GFR 15-29 mL/min/1.73 m2).',
         'Stage 4 chronic kidney disease',
         'required', 'Kidney', 0),
        ('HP:0003774', 'Stage 5 chronic kidney disease', 'RenalInsufficancy',
         'A degree of kidney failure severe enough to require dialysis or kidney transplantation for survival characterized by a severe reduction in glomerular filtration rate (less than 15 ml/min/1.73 m2) and other manifestations including increased serum creatinine.',
         'End stage renal disease, End stage renal failure, Renal failure, endstage, End-stage renal disease, End-stage renal failure, Stage 5 chronic kidney disease, Chronic renal failure',
         'required', 'Kidney', 0),
        ('HP:0033133', 'Renal cortical hyperechogenicity', 'Hyperechogenicity',
         'Increased echogenecity of the kidney cortex.',
         'No synonyms found for this term.',
         'required', 'Kidney', 0),
        ('HP:0000107', 'Renal cyst', 'RenalCysts',
         'A fluid filled sac in the kidney.',
         'Kidney cyst, Cystic kidneys, Cystic kidney disease, Renal cysts',
         'required', 'Kidney', 0),
        ('HP:0000003', 'Multicystic kidney dysplasia', 'MulticysticDysplasticKidney',
         'Multicystic dysplasia of the kidney is characterized by multiple cysts of varying size in the kidney and the absence of a normal pelvicaliceal system. The condition is associated with ureteral or ureteropelvic atresia, and the affected kidney is nonfunctional.',
         'Multicystic kidneys, Multicystic dysplastic kidney, Multicystic renal dysplasia',
         'required', 'Kidney', 0),
        ('HP:0100611', 'Multiple glomerular cysts', 'KidneyBiopsy',
         'The presence of many cysts in the glomerulus of the kidney related to dilatation of the Bowman''s capsule.',
         'Glomerulocystic kidney disease',
         'required', 'Kidney', 0),
        ('ORPHA:2260', 'Oligomeganephronia', 'KidneyBiopsy',
         'Oligomeganephronia is a developmental anomaly of the kidneys, and the most severe form of renal hypoplasia, characterized by a reduction of 80% in nephron number and a marked hypertrophy of the glomeruli and tubules.',
         '',
         'required', 'Kidney', 0),
        ('HP:0000089', 'Renal hypoplasia', 'RenalHypoplasia',
         'Hypoplasia of the kidney.',
         'Hypoplastic kidneys, Small kidneys, Underdeveloped kidneys, Hypoplastic kidney',
         'required', 'Kidney', 0),
        ('HP:0000122', 'Unilateral renal agenesis', 'SolitaryKidney',
         'A unilateral form of agenesis of the kidney.',
         'Absent kidney on one side, Unilateral kidney agenesis, Single kidney, Missing one kidney',
         'required', 'Kidney', 0),
        ('HP:0012210', 'Abnormal renal morphology', 'AntenatalRenalAbnormalities',
         'Any structural anomaly of the kidney.',
         'Abnormal kidney morphology, Kidney malformation, Kidney structure issue, Renal malformation, Structural kidney abnormalities, Abnormally shaped kidney, Structural renal anomalies, Structural anomalies of the renal tract',
         'required', 'Kidney', 0),

        -- Urinary tract
        ('HP:0000079', 'Abnormality of the urinary system', 'UrinaryTractMalformation',
         'An abnormality of the urinary system.',
         'Urinary tract abnormalities, Urinary tract abnormality, Urinary tract anomalies',
         'required', 'Urinary tract', 0),

        -- Genital
        ('HP:0000078', 'Abnormality of the genital system', 'GenitalTractAbnormality',
         'An abnormality of the genital system.',
         'Genital defects, Abnormality of the reproductive system, Genital anomalies, Genital abnormality, Genital abnormalities',
         'required', 'Genital', 0),

        -- Electrolytes and uric acid
        ('HP:0002917', 'Hypomagnesemia', 'Hypomagnesemia',
         'An abnormally decreased magnesium concentration in the blood.',
         'Low blood magnesium levels, Low blood Mg levels',
         'required', 'Electrolytes and uric acid', 0),
        ('HP:0002900', 'Hypokalemia', 'Hypokalemia',
         'An abnormally decreased potassium concentration in the blood.',
         'Low blood potassium levels',
         'required', 'Electrolytes and uric acid', 0),
        ('HP:0002149', 'Hyperuricemia', 'Hyperuricemia',
         'An abnormally high level of uric acid in the blood.',
         'High blood uric acid level, Hyperuricaemia',
         'required', 'Electrolytes and uric acid', 0),
        ('HP:0001997', 'Gout', 'Gout',
         'Recurrent attacks of acute inflammatory arthritis of a joint or set of joints caused by elevated levels of uric acid in the blood which crystallize and are deposited in joints, tendons, and surrounding tissues.',
         'Gouty arthritis',
         'required', 'Electrolytes and uric acid', 0),

        -- Hormones
        ('HP:0004904', 'Maturity-onset diabetes of the young', 'MODY',
         'The term Maturity-onset diabetes of the young (MODY) was initially used for patients diagnosed with fasting hyperglycemia that could be treated without insulin for more than two years, where the initial diagnosis was made at a young age (under 25 years). Thus, MODY combines characteristics of type 1 diabetes (young age at diagnosis) and type 2 diabetes (less insulin dependence than type 1 diabetes). The term MODY is now most often used to refer to a group of monogenic diseases with these characteristics. Here, the term is used to describe hyperglycemia diagnosed at a young age with no or minor insulin dependency, no evidence of insulin resistence, and lack of evidence of autoimmune destruction of the beta cells.',
         'MODY, Maturity onset diabetes of the young',
         'required', 'Hormones', 0),
        ('HP:0002594', 'Pancreatic hypoplasia', 'PancreaticHypoplasia',
         'Hypoplasia of the pancreas.',
         'Hypoplastic pancreas, Underdeveloped pancreas',
         'required', 'Hormones', 0),
        ('HP:0001738', 'Exocrine pancreatic insufficiency', 'ExocrinePancreaticInsufficiency',
         'Impaired function of the exocrine pancreas associated with a reduced ability to digest foods because of lack of digestive enzymes.',
         'Pancreatic insufficiency, Inability to properly digest food due to lack of pancreatic digestive enzymes',
         'required', 'Hormones', 0),
        ('HP:0000843', 'Hyperparathyroidism', 'Hyperparathyroidism',
         'Excessive production of parathyroid hormone (PTH) by the parathyroid glands.',
         'Elevated blood parathyroid hormone level',
         'required', 'Hormones', 0),

        -- Brain (recommended)
        ('HP:0012758', 'Neurodevelopmental delay', 'NeurodevelopmentalDisorder',
         '',
         'No synonyms found for this term.',
         'recommended', 'Brain', 0),
        ('HP:0000708', 'Behavioral abnormality', 'MentalDisease',
         'An abnormality of mental functioning including various affective, behavioural, cognitive and perceptual abnormalities.',
         'Behavioral abnormality, Behavioral symptoms, Behavioural abnormality, Behavioural disturbances, Behavioural/Psychiatric abnormality, Psychiatric disorders, Behavioral problems, Behavioral disturbances, Behavioural symptoms, Behavioural changes, Behavioral disorders, Behavioural problems, Behavioural disorders, Psychiatric disturbances, Behavioral changes, Behavioral/psychiatric abnormalities',
         'recommended', 'Brain', 0),
        ('HP:0001250', 'Seizure', 'Seizures',
         'A seizure is an intermittent abnormality of nervous system physiology characterised by a transient occurrence of signs and/or symptoms due to abnormal excessive or synchronous neuronal activity in the brain.',
         'Epileptic seizure, Epilepsy, Seizures',
         'recommended', 'Brain', 0),
        ('HP:0012443', 'Abnormality of brain morphology', 'BrainAbnormality',
         'A structural abnormality of the brain, which has as its parts the forebrain, midbrain, and hindbrain.',
         'Abnormality of the brain, Abnormal shape of brain',
         'recommended', 'Brain', 0),

        -- Other (recommended)
        ('HP:0001622', 'Premature birth', 'PrematureBirth',
         'The birth of a baby of less than 37 weeks of gestational age.',
         'Premature birth, Premature delivery of affected infants, Shortened gestation time, Premature delivery, Preterm delivery',
         'recommended', 'Other', 0),
        ('HP:0001627', 'Abnormal heart morphology', 'CongenitalCardiacAnomalies',
         'Any structural anomaly of the heart.',
         'Abnormality of the heart, Congenital heart defects, Congenital heart defect, Cardiac anomalies, Abnormally shaped heart, Heart defect, Abnormality of cardiac morphology, Cardiac anomaly, Cardiac abnormality',
         'recommended', 'Other', 0),
        ('HP:0000478', 'Abnormality of the eye', 'EyeAbnormality',
         'Any abnormality of the eye, including location, spacing, and intraocular abnormalities.',
         'Eye disease, Abnormal eye, Abnormality of the eye',
         'recommended', 'Other', 0),
        ('HP:0004322', 'Short stature', 'ShortStature',
         'A height below that which is expected according to age and gender norms. Although there is no universally accepted definition of short stature, many refer to "short stature" as height more than 2 standard deviations below the mean for age and gender (or below the 3rd percentile for age and gender dependent norms).',
         'Decreased body height, Small stature, Stature below 3rd percentile, Height less than 3rd percentile, Short stature',
         'recommended', 'Other', 0),
        ('HP:0033127', 'Abnormality of the musculoskeletal system', 'MusculoskeletalFeatures',
         'An anomaly of the musculoskeletal system, which consists of the bones of the skeleton, muscles, cartilage, tendons, ligaments, joints, and other connective tissue. The musculoskeletal system supports the weight of the body, maintains body position and produces movements of the body or of parts of the body.',
         'No synonyms found for this term.',
         'recommended', 'Other', 0),
        ('HP:0001999', 'Abnormal facial shape', 'DysmorphicFeatures',
         'An abnormal morphology (form) of the face or its components.',
         'Malformation of face, Abnormal morphology of the face, Distortion of face, Unusual facies, Funny looking face, Deformity of face, Dysmorphic facies, Dysmorphic facial features, Distinctive facies, Facial dysmorphism, Abnormal facial shape, Unusual facial appearance',
         'recommended', 'Other', 0),
        ('HP:0002910', 'Elevated hepatic transaminase', 'ElevatedHepaticTransaminase',
         'Elevations of the levels of SGOT and SGPT in the serum. SGOT (serum glutamic oxaloacetic transaminase) and SGPT (serum glutamic pyruvic transaminase) are transaminases primarily found in the liver and heart and are released into the bloodstream as the result of liver or heart damage. SGOT and SGPT are used clinically mainly as markers of liver damage.',
         'Abnormal liver function, Increased liver enzymes, Elevated transaminases, Increased transaminases, Elevated serum transaminases, Abnormal liver enzymes, Raised liver enzymes, Subclinical abnormal liver function tests, Abnormal liver function tests, Elevated liver enzymes, High liver enzymes, Increased liver function tests, Elevated liver function tests',
         'required', 'Other', 0),
        ('HP:0031865', 'Abnormal liver physiology', 'AbnormalLiverPhysiology',
         'Any functional anomaly of the liver.',
         'Abnormal hepatic physiology',
         'required', 'Other', 0)
    """)


def downgrade() -> None:
    """Remove phenotype metadata columns."""
    op.execute("""
        ALTER TABLE hpo_terms_lookup
        DROP COLUMN IF EXISTS category,
        DROP COLUMN IF EXISTS description,
        DROP COLUMN IF EXISTS synonyms,
        DROP COLUMN IF EXISTS recommendation,
        DROP COLUMN IF EXISTS "group"
    """)
