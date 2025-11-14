/**
 * VeeValidate schemas for phenopacket form validation.
 *
 * Uses Yup for declarative, reusable validation following GA4GH Phenopackets v2 standard.
 */

import * as yup from 'yup';

// Subject validation schema
export const subjectSchema = yup.object({
  id: yup
    .string()
    .required('Subject ID is required')
    .matches(/^[A-Za-z0-9_-]+$/, 'Subject ID must be alphanumeric'),

  sex: yup
    .string()
    .required('Sex is required')
    .oneOf(['MALE', 'FEMALE', 'OTHER_SEX', 'UNKNOWN_SEX'], 'Invalid sex value'),

  timeAtLastEncounter: yup.object({
    age: yup.object({
      iso8601duration: yup.string().matches(/^P/, 'Invalid ISO8601 duration format'),
    }),
  }),
});

// Phenotypic feature validation schema
export const phenotypicFeatureSchema = yup.object({
  type: yup.object({
    id: yup
      .string()
      .required('HPO term is required')
      .matches(/^HP:\d{7}$/, 'Invalid HPO term format (e.g., HP:0000107)'),
    label: yup.string().required('HPO term label is required'),
  }),

  excluded: yup.boolean(),

  modifiers: yup.array().of(
    yup.object({
      id: yup.string().matches(/^HP:\d{7}$/, 'Invalid HPO term format'),
      label: yup.string(),
    })
  ),

  onset: yup.object({
    id: yup.string().matches(/^HP:\d{7}$/, 'Invalid HPO onset term'),
    label: yup.string(),
  }),
});

// Interpretation (variant) validation schema
export const interpretationSchema = yup.object({
  id: yup.string().required('Interpretation ID is required'),

  progressStatus: yup
    .string()
    .oneOf(['SOLVED', 'UNSOLVED', 'IN_PROGRESS', 'UNKNOWN'], 'Invalid progress status'),

  diagnosis: yup.object({
    disease: yup.object({
      id: yup
        .string()
        .required('Disease term is required')
        .matches(/^(MONDO|OMIM):\d+$/, 'Invalid disease ID format (e.g., MONDO:0019267)'),
      label: yup.string().required('Disease label is required'),
    }),
    genomicInterpretations: yup.array().of(
      yup.object({
        subjectOrBiosampleId: yup.string().required('Subject ID is required'),
        interpretationStatus: yup
          .string()
          .oneOf(
            ['CAUSATIVE', 'CONTRIBUTORY', 'CANDIDATE', 'UNCERTAIN_SIGNIFICANCE', 'REJECTED'],
            'Invalid interpretation status'
          ),
        variantInterpretation: yup.object({
          variationDescriptor: yup.object({
            id: yup.string().required('Variant ID is required'),
            variation: yup.object().required('Variant details are required'),
            label: yup.string().required('Variant label is required'),
            moleculeContext: yup
              .string()
              .oneOf(['genomic', 'transcript', 'protein'], 'Invalid molecule context'),
          }),
        }),
      })
    ),
  }),
});

// Complete phenopacket validation schema
export const phenopacketSchema = yup.object({
  id: yup
    .string()
    .required('Phenopacket ID is required')
    .matches(/^phenopacket-[\w-]+$/, 'Phenopacket ID must start with "phenopacket-"'),

  subject: subjectSchema.required('Subject information is required'),

  phenotypicFeatures: yup
    .array()
    .of(phenotypicFeatureSchema)
    .min(1, 'At least one phenotypic feature is required'),

  interpretations: yup.array().of(interpretationSchema),

  metaData: yup.object({
    created: yup.string().required('Creation timestamp is required'),
    createdBy: yup.string().required('Creator identifier is required'),
    resources: yup
      .array()
      .of(
        yup.object({
          id: yup.string().required(),
          name: yup.string().required(),
          url: yup.string().url(),
          version: yup.string(),
          namespacePrefix: yup.string(),
        })
      )
      .min(1, 'At least one ontology resource is required'),
  }),
});

// Variant input validation (for VEP annotation)
export const variantInputSchema = yup.object({
  variant: yup
    .string()
    .required('Variant is required')
    .test(
      'variant-format',
      'Invalid variant format. Use VCF (chr-pos-ref-alt), HGVS, or rsID',
      (value) => {
        if (!value) return false;

        // VCF format: 17-36459258-A-G
        const vcfPattern = /^\d{1,2}[XY]?-\d+-[ACGT]+-[ACGT]+$/i;

        // HGVS format: NM_000458.4:c.544+1G>A or p.Gln136Ter
        const hgvsPattern = /^(NM_|NP_|ENST|ENSP)[\w.:]+[>*]?[\w]+$/;

        // rsID format: rs56116432
        const rsidPattern = /^rs\d+$/;

        return vcfPattern.test(value) || hgvsPattern.test(value) || rsidPattern.test(value);
      }
    ),
});
