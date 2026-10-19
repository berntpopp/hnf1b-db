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

function isWholeItemPath(path, pattern) {
  return pattern.test(path);
}

function findVariantInfoFromObject(obj) {
  if (!obj || typeof obj !== 'object') return { gene: 'HNF1B', label: '' };
  const gInterp =
    obj.diagnosis?.genomicInterpretations?.[0] || obj.genomicInterpretations?.[0] || obj;
  const desc =
    gInterp?.variantInterpretation?.variationDescriptor ||
    gInterp?.variationDescriptor ||
    obj.variationDescriptor;
  const gene =
    desc?.geneContext?.value ||
    desc?.geneContext?.symbol ||
    gInterp?.variantInterpretation?.geneContext?.value ||
    'HNF1B';
  const label = desc?.label || desc?.id || '';
  return { gene, label };
}

function findVariantInfo(content, path) {
  const index = extractIndexFromPath(path, '/(?:interpretations|variantInterpretations|variants)');
  if (index === null) return { gene: 'HNF1B', label: '' };

  const interp =
    content?.interpretations?.[index] ||
    content?.variantInterpretations?.[index] ||
    content?.variants?.[index];

  if (!interp) return { gene: 'HNF1B', label: '' };

  const giMatch = path.match(/\/genomicInterpretations\/(\d+)/);
  const giIndex = giMatch ? parseInt(giMatch[1], 10) : 0;

  const gInterp =
    interp.diagnosis?.genomicInterpretations?.[giIndex] ||
    interp.genomicInterpretations?.[giIndex] ||
    interp;

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

function resolveArrayItem(operation, index, key, baselineContent, candidateContent, before, after) {
  if (operation === 'removed') {
    return (
      (typeof before === 'object' && before !== null ? before : null) ||
      (index !== null ? baselineContent[key]?.[index] || candidateContent[key]?.[index] : null) ||
      (typeof after === 'object' && after !== null ? after : null) ||
      {}
    );
  }
  return (
    (index !== null ? candidateContent[key]?.[index] || baselineContent[key]?.[index] : null) ||
    (typeof after === 'object' && after !== null ? after : null) ||
    (typeof before === 'object' && before !== null ? before : null) ||
    {}
  );
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
      const featureKey = path.startsWith('/phenotypic_features')
        ? 'phenotypic_features'
        : 'phenotypicFeatures';
      const isWholeFeature = isWholeItemPath(
        path,
        /^\/(?:phenotypicFeatures|phenotypic_features)\/\d+$/
      );
      const feature = isWholeFeature
        ? resolveArrayItem(
            operation,
            index,
            featureKey,
            baselineContent,
            candidateContent,
            before,
            after
          )
        : (index !== null
            ? operation === 'removed'
              ? baselineContent[featureKey]?.[index] || candidateContent[featureKey]?.[index]
              : candidateContent[featureKey]?.[index] || baselineContent[featureKey]?.[index]
            : null) || {};

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
      } else if (isWholeFeature && operation === 'added') {
        const isExcluded = feature.excluded === true;
        const text = isExcluded ? `Excluded: ${termWithParen}` : `Added: ${termWithParen}`;
        phenotypes.push({ text, operation, change });
      } else if (isWholeFeature && operation === 'removed') {
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
      const isWholeVariant = isWholeItemPath(
        path,
        /^\/(?:interpretations|variantInterpretations|variants)\/\d+(?:\/(?:diagnosis\/)?genomicInterpretations\/\d+)?$/
      );
      const primarySide = operation === 'removed' ? baselineContent : candidateContent;
      const fallbackSide = operation === 'removed' ? candidateContent : baselineContent;
      const primaryInfo = findVariantInfo(primarySide, path);
      const fallbackInfo = findVariantInfo(fallbackSide, path);
      const payloadInfo = findVariantInfoFromObject(operation === 'removed' ? before : after);
      const vInfo = primaryInfo.label
        ? primaryInfo
        : payloadInfo.label
          ? payloadInfo
          : fallbackInfo;

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
      } else if (isWholeVariant && operation === 'added') {
        variants.push({
          text: `Added variant: ${varPrefix} (${formatValueBrief(after)})`,
          operation,
          change,
        });
      } else if (isWholeVariant && operation === 'removed') {
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
        const isWholeDisease = isWholeItemPath(path, /^\/diseases\/\d+$/);
        const disease = isWholeDisease
          ? resolveArrayItem(
              operation,
              index,
              'diseases',
              baselineContent,
              candidateContent,
              before,
              after
            )
          : (index !== null
              ? operation === 'removed'
                ? baselineContent.diseases?.[index] || candidateContent.diseases?.[index]
                : candidateContent.diseases?.[index] || baselineContent.diseases?.[index]
              : null) || {};

        const diseaseName = disease.term?.label || disease.term?.id || disease.id || 'Disease';

        if (path.includes('onset')) {
          subject.push({
            text: `Disease onset: ${diseaseName} (${formatValueBrief(before)} -> ${formatValueBrief(after)})`,
            operation,
            change,
          });
        } else if (isWholeDisease && operation === 'added') {
          subject.push({
            text: `Added disease: ${diseaseName}`,
            operation,
            change,
          });
        } else if (isWholeDisease && operation === 'removed') {
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
        const isWholeMeasurement = isWholeItemPath(path, /^\/measurements\/\d+$/);
        const meas = isWholeMeasurement
          ? resolveArrayItem(
              operation,
              index,
              'measurements',
              baselineContent,
              candidateContent,
              before,
              after
            )
          : (index !== null
              ? operation === 'removed'
                ? baselineContent.measurements?.[index] || candidateContent.measurements?.[index]
                : candidateContent.measurements?.[index] || baselineContent.measurements?.[index]
              : null) || {};

        const assayName = meas.assay?.label || meas.assay?.id || meas.id || 'Measurement';

        if (path.endsWith('/value')) {
          other.push({
            text: `Measurement ${assayName} value: ${formatValueBrief(before)} -> ${formatValueBrief(after)}`,
            operation,
            change,
          });
        } else if (isWholeMeasurement && operation === 'added') {
          other.push({
            text: `Added measurement: ${assayName}`,
            operation,
            change,
          });
        } else if (isWholeMeasurement && operation === 'removed') {
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
