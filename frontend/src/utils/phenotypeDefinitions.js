const DEFINITIONS = [
  ['RenalInsufficancy', 'ckd-unspecified', 'HP:0012622', 'chronic kidney disease, not specified'],
  ['RenalInsufficancy', 'ckd-stage-1', 'HP:0012623', 'Stage 1 chronic kidney disease'],
  ['RenalInsufficancy', 'ckd-stage-2', 'HP:0012624', 'Stage 2 chronic kidney disease'],
  ['RenalInsufficancy', 'ckd-stage-3', 'HP:0012625', 'Stage 3 chronic kidney disease'],
  ['RenalInsufficancy', 'ckd-stage-4', 'HP:0012626', 'Stage 4 chronic kidney disease'],
  ['RenalInsufficancy', 'ckd-stage-5', 'HP:0003774', 'Stage 5 chronic kidney disease'],
  [
    'Hyperechogenicity',
    'renal-cortical-hyperechogenicity',
    'HP:0033132',
    'Renal cortical hyperechogenicity',
  ],
  ['RenalCysts', 'renal-cyst', 'HP:0000107', 'Renal cyst'],
  [
    'MulticysticDysplasticKidney',
    'multicystic-kidney-dysplasia',
    'HP:0000003',
    'Multicystic kidney dysplasia',
  ],
  ['KidneyBiopsy', 'multiple-glomerular-cysts', 'HP:0100611', 'Multiple glomerular cysts'],
  ['KidneyBiopsy', 'oligomeganephronia', 'ORPHA:2260', 'Oligomeganephronia'],
  ['RenalHypoplasia', 'renal-hypoplasia', 'HP:0000089', 'Renal hypoplasia'],
  ['SolitaryKidney', 'unilateral-renal-agenesis', 'HP:0000122', 'Unilateral renal agenesis'],
  [
    'UrinaryTractMalformation',
    'urinary-system-abnormality',
    'HP:0000079',
    'Abnormality of the urinary system',
  ],
  [
    'GenitalTractAbnormality',
    'genital-system-abnormality',
    'HP:0000078',
    'Abnormality of the genital system',
  ],
  [
    'AntenatalRenalAbnormalities',
    'abnormal-renal-morphology',
    'HP:0012210',
    'Abnormal renal morphology',
  ],
  ['Hypomagnesemia', 'hypomagnesemia', 'HP:0002917', 'Hypomagnesemia'],
  ['Hypokalemia', 'hypokalemia', 'HP:0002900', 'Hypokalemia'],
  ['Hyperuricemia', 'hyperuricemia', 'HP:0002149', 'Hyperuricemia'],
  ['Gout', 'gout', 'HP:0001997', 'Gout'],
  ['MODY', 'maturity-onset-diabetes-young', 'HP:0004904', 'Maturity-onset diabetes of the young'],
  ['PancreaticHypoplasia', 'pancreatic-hypoplasia', 'HP:0002594', 'Pancreatic hypoplasia'],
  [
    'ExocrinePancreaticInsufficiency',
    'exocrine-pancreatic-insufficiency',
    'HP:0001738',
    'Exocrine pancreatic insufficiency',
  ],
  ['Hyperparathyroidism', 'hyperparathyroidism', 'HP:0000843', 'Hyperparathyroidism'],
  [
    'NeurodevelopmentalDisorder',
    'neurodevelopmental-delay',
    'HP:0012758',
    'Neurodevelopmental delay',
  ],
  ['MentalDisease', 'behavioral-abnormality', 'HP:0000708', 'Behavioral abnormality'],
  ['Seizures', 'seizure', 'HP:0001250', 'Seizure'],
  [
    'BrainAbnormality',
    'abnormal-brain-morphology',
    'HP:0012443',
    'Abnormality of brain morphology',
  ],
  ['PrematureBirth', 'premature-birth', 'HP:0001622', 'Premature birth'],
  [
    'CongenitalCardiacAnomalies',
    'abnormal-heart-morphology',
    'HP:0001627',
    'Abnormal heart morphology',
  ],
  ['EyeAbnormality', 'abnormality-of-eye', 'HP:0000478', 'Abnormality of the eye'],
  ['ShortStature', 'short-stature', 'HP:0004322', 'Short stature'],
  [
    'MusculoskeletalFeatures',
    'musculoskeletal-system-abnormality',
    'HP:0033127',
    'Abnormality of the musculoskeletal system',
  ],
  ['DysmorphicFeatures', 'abnormal-facial-shape', 'HP:0001999', 'Abnormal facial shape'],
  [
    'ElevatedHepaticTransaminase',
    'elevated-hepatic-transaminase',
    'HP:0002910',
    'Elevated hepatic transaminase',
  ],
  [
    'AbnormalLiverPhysiology',
    'abnormal-liver-physiology',
    'HP:0031865',
    'Abnormal liver physiology',
  ],
];

export const PHENOTYPE_DEFINITIONS = Object.freeze(
  DEFINITIONS.map(([column, definitionId, id, label]) => ({
    column,
    definitionId,
    term: { id, label },
  }))
);

export const definitionsForColumn = (column) =>
  PHENOTYPE_DEFINITIONS.filter((definition) => definition.column === column);
