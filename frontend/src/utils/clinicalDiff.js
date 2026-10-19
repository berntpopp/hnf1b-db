import { sanitize } from '@/utils/sanitize';

/**
 * Format a value briefly for clinical summaries, ensuring XSS safety.
 *
 * @param {*} val
 * @returns {string}
 */
export function formatValueBrief(val) {
  if (val === null || val === undefined) return 'None';
  if (typeof val === 'string') return sanitize(val);
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (typeof val === 'object') {
    if (val.label && val.id) return `${sanitize(val.label)} (${sanitize(val.id)})`;
    if (val.label) return sanitize(val.label);
    if (val.id) return sanitize(val.id);
    if (val.iso8601duration) return sanitize(val.iso8601duration);
    if (val.age?.iso8601duration) return sanitize(val.age.iso8601duration);
    return sanitize(JSON.stringify(val));
  }
  return sanitize(String(val));
}

function extractIndexFromPath(path, prefix) {
  const regex = new RegExp(`^${prefix}/(\\d+)`);
  const match = path.match(regex);
  return match ? parseInt(match[1], 10) : null;
}

function findVariantInfo(content, path) {
  const index = extractIndexFromPath(path, '/(?:interpretations|variantInterpretations|variants)');
  if (index === null) return { gene: 'HNF1B', label: '' };

  const interp =
    content?.interpretations?.[index] ||
    content?.variantInterpretations?.[index] ||
    content?.variants?.[index];

  if (!interp) return { gene: 'HNF1B', label: '' };

  const gInterp =
    interp.diagnosis?.genomicInterpretations?.[0] || interp.genomicInterpretations?.[0] || interp;

  const desc =
    gInterp?.variantInterpretation?.variationDescriptor ||
    gInterp?.variationDescriptor ||
    interp.variationDescriptor;

  const gene =
    desc?.geneContext?.value ||
    desc?.geneContext?.symbol ||
    gInterp?.variantInterpretation?.geneContext?.value ||
    'HNF1B';

  const label = desc?.label || desc?.id || '';
  return { gene, label };
}

/**
 * Resolves human-friendly clinical summary cards from raw changes and context.
 *
 * @param {Array} changes
 * @param {Object|null} baseline
 * @param {Object|null} candidate
 * @returns {Array} List of category cards with items
 */
export function resolveClinicalSummaries(changes = [], baseline = null, candidate = null) {
  if (!changes || changes.length === 0) return [];

  const baselineContent = baseline?.content || baseline || {};
  const candidateContent = candidate?.content || candidate || {};

  const phenotypes = [];
  const variants = [];
  const subject = [];
  const other = [];

  for (const change of changes) {
    const { section, operation, path, before, after } = change;

    // 1. Phenotypes
    if (
      section === 'Phenotypes' ||
      path.startsWith('/phenotypicFeatures') ||
      path.startsWith('/phenotypic_features')
    ) {
      const index = extractIndexFromPath(path, '/(?:phenotypicFeatures|phenotypic_features)');
      const feature =
        (index !== null
          ? candidateContent.phenotypicFeatures?.[index] ||
            baselineContent.phenotypicFeatures?.[index]
          : null) ||
        (typeof after === 'object' && after !== null ? after : null) ||
        (typeof before === 'object' && before !== null ? before : null) ||
        {};

      const termId = feature.type?.id || feature.id || '';
      const termLabel = feature.type?.label || feature.label || '';
      const termDisplay = termLabel
        ? termId
          ? `${termId} — ${termLabel}`
          : termLabel
        : termId || (index !== null ? `Feature #${index}` : 'Phenotype');
      const termWithParen = termLabel
        ? termId
          ? `${termLabel} (${termId})`
          : termLabel
        : termId || 'Phenotype';

      if (path.endsWith('/excluded')) {
        const beforeState = before ? 'Excluded' : 'Present';
        const afterState = after ? 'Excluded' : 'Present';
        phenotypes.push({
          text: `${termDisplay} (${beforeState} -> ${afterState})`,
          operation,
          change,
        });
      } else if (operation === 'added') {
        const isExcluded = feature.excluded === true;
        const text = isExcluded ? `Excluded: ${termWithParen}` : `Added: ${termWithParen}`;
        phenotypes.push({ text, operation, change });
      } else if (operation === 'removed') {
        phenotypes.push({
          text: `Removed: ${termWithParen}`,
          operation,
          change,
        });
      } else {
        const prop = path.split('/').pop();
        phenotypes.push({
          text: `${termDisplay}: ${prop} changed (${formatValueBrief(before)} -> ${formatValueBrief(after)})`,
          operation,
          change,
        });
      }
    }
    // 2. Variants / ACMG
    else if (
      section === 'Variants/Interpretations' ||
      path.startsWith('/interpretations') ||
      path.startsWith('/variants') ||
      path.startsWith('/variantInterpretations')
    ) {
      const vInfo = findVariantInfo(candidateContent, path).label
        ? findVariantInfo(candidateContent, path)
        : findVariantInfo(baselineContent, path);

      const varPrefix = vInfo.label ? `${vInfo.gene} ${vInfo.label}` : vInfo.gene;

      if (path.includes('acmgPathogenicityClassification')) {
        variants.push({
          text: `${varPrefix} — ACMG classification: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      } else if (path.includes('interpretationStatus')) {
        variants.push({
          text: `${varPrefix} — Interpretation status: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      } else if (path.includes('therapeuticActionability')) {
        variants.push({
          text: `${varPrefix} — Therapeutic actionability: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      } else if (path.includes('segregation')) {
        variants.push({
          text: `${varPrefix} — Segregation: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      } else if (operation === 'added') {
        variants.push({
          text: `Added variant: ${varPrefix} (${formatValueBrief(after)})`,
          operation,
          change,
        });
      } else if (operation === 'removed') {
        variants.push({
          text: `Removed variant: ${varPrefix} (${formatValueBrief(before)})`,
          operation,
          change,
        });
      } else {
        const prop = path.split('/').pop();
        variants.push({
          text: `${varPrefix}: ${prop} changed (${formatValueBrief(before)} -> ${formatValueBrief(after)})`,
          operation,
          change,
        });
      }
    }
    // 3. Subject / Diseases onset
    else if (
      section === 'Subject' ||
      section === 'Diseases' ||
      path.startsWith('/subject') ||
      path.startsWith('/diseases')
    ) {
      if (path === '/subject/id') {
        subject.push({
          text: `Subject ID: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      } else if (path === '/subject/sex') {
        subject.push({
          text: `Subject sex: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      } else if (path.includes('timeAtLastEncounter')) {
        subject.push({
          text: `Time at last encounter: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      } else if (path.startsWith('/diseases')) {
        const index = extractIndexFromPath(path, '/diseases');
        const disease =
          (index !== null
            ? candidateContent.diseases?.[index] || baselineContent.diseases?.[index]
            : null) ||
          (typeof after === 'object' && after !== null ? after : null) ||
          (typeof before === 'object' && before !== null ? before : null) ||
          {};

        const diseaseName = disease.term?.label || disease.term?.id || disease.id || 'Disease';

        if (path.includes('onset')) {
          subject.push({
            text: `Disease onset: ${diseaseName} (${formatValueBrief(before)} -> ${formatValueBrief(after)})`,
            operation,
            change,
          });
        } else if (operation === 'added') {
          subject.push({
            text: `Added disease: ${diseaseName}`,
            operation,
            change,
          });
        } else if (operation === 'removed') {
          subject.push({
            text: `Removed disease: ${diseaseName}`,
            operation,
            change,
          });
        } else {
          const prop = path.split('/').pop();
          subject.push({
            text: `Disease ${diseaseName}: ${prop} changed (${formatValueBrief(before)} -> ${formatValueBrief(after)})`,
            operation,
            change,
          });
        }
      } else {
        const prop = path.replace('/subject/', '');
        subject.push({
          text: `Subject ${prop}: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      }
    }
    // 4. Measurements & other
    else {
      if (path.startsWith('/measurements')) {
        const index = extractIndexFromPath(path, '/measurements');
        const meas =
          (index !== null
            ? candidateContent.measurements?.[index] || baselineContent.measurements?.[index]
            : null) ||
          (typeof after === 'object' && after !== null ? after : null) ||
          (typeof before === 'object' && before !== null ? before : null) ||
          {};

        const assayName = meas.assay?.label || meas.assay?.id || meas.id || 'Measurement';

        if (path.endsWith('/value')) {
          other.push({
            text: `Measurement ${assayName} value: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
            operation,
            change,
          });
        } else if (operation === 'added') {
          other.push({
            text: `Added measurement: ${assayName}`,
            operation,
            change,
          });
        } else if (operation === 'removed') {
          other.push({
            text: `Removed measurement: ${assayName}`,
            operation,
            change,
          });
        } else {
          const prop = path.split('/').pop();
          other.push({
            text: `Measurement ${assayName}: ${prop} changed (${formatValueBrief(before)} -> ${formatValueBrief(after)})`,
            operation,
            change,
          });
        }
      } else {
        const prop = path.replace(/^\//, '');
        other.push({
          text: `${prop}: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
          operation,
          change,
        });
      }
    }
  }

  const categories = [];

  if (phenotypes.length > 0) {
    categories.push({
      id: 'phenotypes',
      title: 'Phenotypes Added / Removed / Excluded',
      icon: 'mdi-format-list-checks',
      color: 'primary',
      items: phenotypes,
    });
  }

  if (variants.length > 0) {
    categories.push({
      id: 'variants',
      title: 'Variant / ACMG Classification Changes',
      icon: 'mdi-dna',
      color: 'secondary',
      items: variants,
    });
  }

  if (subject.length > 0) {
    categories.push({
      id: 'subject',
      title: 'Subject / Onset Deltas',
      icon: 'mdi-account-clock-outline',
      color: 'teal',
      items: subject,
    });
  }

  if (other.length > 0) {
    categories.push({
      id: 'other',
      title: 'Measurements & Other Clinical Changes',
      icon: 'mdi-chart-bell-curve',
      color: 'medium-emphasis',
      items: other,
    });
  }

  return categories;
}
