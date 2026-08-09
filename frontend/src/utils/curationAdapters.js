const LATERALITY = Object.freeze({
  bilateral: [{ id: 'HP:0012832', label: 'Bilateral' }],
  unilateral: [{ id: 'HP:0012833', label: 'Unilateral' }],
  'unilateral-left': [
    { id: 'HP:0012833', label: 'Unilateral' },
    { id: 'HP:0012835', label: 'Left' },
  ],
  'unilateral-right': [
    { id: 'HP:0012833', label: 'Unilateral' },
    { id: 'HP:0012834', label: 'Right' },
  ],
  none: [],
});

const STATUS_WITH_FINDINGS = new Set(['PRESENT', 'EXCLUDED']);

export const ASSESSMENT_STATES = Object.freeze([
  { value: 'PRESENT', label: 'Present' },
  { value: 'EXCLUDED', label: 'Absent' },
  { value: 'NOT_REPORTED', label: 'Not reported' },
  { value: 'NOT_APPLICABLE', label: 'Not applicable' },
  { value: 'INDETERMINATE', label: 'Unresolved' },
  { value: 'NOT_ASSESSED', label: 'Not assessed' },
]);

export const LATERALITY_OPTIONS = Object.freeze([
  { value: 'none', label: 'None' },
  { value: 'bilateral', label: 'Bilateral' },
  { value: 'unilateral', label: 'Unilateral, side unknown' },
  { value: 'unilateral-left', label: 'Unilateral, left' },
  { value: 'unilateral-right', label: 'Unilateral, right' },
]);

export function cloneObservation(observation) {
  // Ledger DTOs are JSON by contract. JSON cloning also unwraps Vue's nested
  // reactive proxies, which structuredClone rejects with DataCloneError.
  return observation === undefined ? undefined : JSON.parse(JSON.stringify(observation));
}

export function updateObservedValue(observedValue, value) {
  return { ...(observedValue || {}), value };
}

export function setAssessmentStatus(assessment, assessmentStatus) {
  const next = cloneObservation(assessment);
  if (STATUS_WITH_FINDINGS.has(assessmentStatus) && !next.findings?.length) return next;
  next.curationStatus = assessmentStatus ? 'CURATED' : 'UNCURATED';
  next.assessmentStatus = assessmentStatus || null;
  if (!STATUS_WITH_FINDINGS.has(assessmentStatus)) next.findings = [];
  return next;
}

export function getLaterality(assessment) {
  const ids = new Set(assessment?.findings?.[0]?.modifiers?.map((term) => term.id) || []);
  if (ids.has('HP:0012832')) return 'bilateral';
  if (ids.has('HP:0012833') && ids.has('HP:0012835')) return 'unilateral-left';
  if (ids.has('HP:0012833') && ids.has('HP:0012834')) return 'unilateral-right';
  if (ids.has('HP:0012833')) return 'unilateral';
  return 'none';
}

export function setLaterality(assessment, value) {
  const next = cloneObservation(assessment);
  const modifiers = LATERALITY[value] || LATERALITY.none;
  next.findings = (next.findings || []).map((finding) => ({
    ...finding,
    modifiers: cloneObservation(modifiers),
  }));
  return next;
}

export function assessmentCompleteness(assessments = []) {
  return {
    filled: assessments.filter((item) => item.curationStatus === 'CURATED').length,
    total: assessments.length,
  };
}

function displayPublication(publication) {
  return [
    publication?.pmid ? `PMID:${publication.pmid}` : '',
    publication?.doi ? `DOI:${publication.doi}` : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

function observedCandidate(observation, conflictKey) {
  if (conflictKey === 'subject:sex') return observation.identifiers?.sex;
  if (conflictKey?.startsWith('phenotype:')) {
    const parts = conflictKey.split(':');
    const kind = parts.at(-1);
    const termId = parts.slice(1, -1).join(':');
    const assessment = observation.phenotypes?.find((item) =>
      item.findings?.some((finding) => finding.term?.id === termId)
    );
    if (!assessment) return null;
    if (kind === 'modifiers') {
      const modifiers = assessment.findings.flatMap((finding) => finding.modifiers || []);
      return {
        raw: assessment.rawValue,
        value: modifiers.map((term) => term.label).join(' + '),
        evidence: assessment.evidence || [],
      };
    }
    return {
      raw: assessment.rawValue,
      value: assessment.assessmentStatus,
      evidence: assessment.evidence || [],
    };
  }
  if (conflictKey?.startsWith('variant:')) {
    const parts = conflictKey.split(':');
    const field = parts.at(-1);
    const descriptorId = parts.slice(1, -1).join(':');
    if (observation.variant?.normalized?.id !== descriptorId) return null;
    if (field === 'contribution') return observation.classification?.contribution || null;
    if (field === 'acmg') return observation.classification?.verdict || null;
  }
  return null;
}

function jsonEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function plainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Merge one report observation against the exact baseline on which it was edited.
 * Arrays are deliberately atomic: silently combining reordered evidence arrays is unsafe.
 */
export function threeWayObservationMerge(base, local, server, decisions = {}, path = '') {
  if (jsonEqual(local, server)) return { merged: cloneObservation(local), conflicts: [] };
  if (jsonEqual(local, base)) return { merged: cloneObservation(server), conflicts: [] };
  if (jsonEqual(server, base)) return { merged: cloneObservation(local), conflicts: [] };

  if (plainObject(base) && plainObject(local) && plainObject(server)) {
    const merged = {};
    const conflicts = [];
    const keys = new Set([...Object.keys(base), ...Object.keys(local), ...Object.keys(server)]);
    for (const key of keys) {
      const childPath = path ? `${path}.${key}` : key;
      const child = threeWayObservationMerge(
        base[key],
        local[key],
        server[key],
        decisions,
        childPath
      );
      if (child.merged !== undefined) merged[key] = child.merged;
      conflicts.push(...child.conflicts);
    }
    return { merged, conflicts };
  }

  const decision = decisions[path];
  if (decision === 'local' || decision === 'server') {
    return { merged: cloneObservation(decision === 'local' ? local : server), conflicts: [] };
  }
  return {
    merged: cloneObservation(server),
    conflicts: [
      {
        path,
        base: cloneObservation(base),
        local: cloneObservation(local),
        server: cloneObservation(server),
      },
    ],
  };
}

function observationWithActiveCorrections(observation, corrections) {
  const next = cloneObservation(observation);
  const targets = correctionTargets(observation, corrections);
  if (targets.some((target) => !target.chainValid)) return null;
  for (const target of targets.filter((item) => item.supersedesCorrectionId)) {
    let current = next;
    for (const segment of target.path.split('.')) current = current?.[segment];
    if (current && typeof current === 'object') current.value = cloneObservation(target.value);
  }
  return next;
}

export function conflictCandidates(issue, observations = [], corrections = []) {
  return observations.flatMap((observation) => {
    const activeObservation = observationWithActiveCorrections(observation, corrections);
    if (!activeObservation) return [];
    const candidate = observedCandidate(activeObservation, issue.conflictKey);
    if (!candidate) return [];
    return [
      {
        observationId: observation.observationId,
        reportId: observation.identifiers?.reportId || observation.observationId,
        publication: displayPublication(observation.publication),
        reviewedOn: observation.sourceReview?.reviewedOn || '',
        reviewer: observation.sourceReview?.reviewerDisplayLabel || '',
        raw: candidate.raw ?? '',
        value: candidate.value ?? '',
        evidence: cloneObservation(candidate.evidence || []),
      },
    ];
  });
}

export function projectionSummary(projection = {}) {
  const phenopacket = projection.phenopacket || {};
  return {
    subjectId: phenopacket.subject?.id || '',
    sex: phenopacket.subject?.sex || 'UNKNOWN_SEX',
    phenotypeCount: phenopacket.phenotypicFeatures?.length || 0,
    variantCount: phenopacket.interpretations?.length || 0,
    references: (phenopacket.metaData?.externalReferences || []).map((item) => item.id),
    conflictCount: projection.issues?.length || 0,
    outputDigest: projection.outputDigest || '',
  };
}

export function curationIssues(error) {
  const detail = error?.response?.data?.detail;
  return Array.isArray(detail?.errors) ? detail.errors : [];
}

const escapePointer = (value) => `${value}`.replaceAll('~', '~0').replaceAll('/', '~1');

export function correctionTargets(observation, corrections = []) {
  const targets = [];
  function visit(value, segments = []) {
    if (!value || typeof value !== 'object') return;
    if (
      Object.prototype.hasOwnProperty.call(value, 'raw') &&
      Object.prototype.hasOwnProperty.call(value, 'sourceStatus') &&
      Object.prototype.hasOwnProperty.call(value, 'value')
    ) {
      const jsonPointer = `/observationsById/${escapePointer(observation.observationId)}/${segments
        .map(escapePointer)
        .join('/')}/value`;
      const chain = corrections.filter((correction) => correction.jsonPointer === jsonPointer);
      const supersededIds = new Set(
        chain.map((correction) => correction.supersedesCorrectionId).filter(Boolean)
      );
      const heads = chain.filter((correction) => !supersededIds.has(correction.correctionId));
      const head = heads.length === 1 ? heads[0] : null;
      targets.push({
        path: segments.join('.'),
        jsonPointer,
        storedValue: cloneObservation(value.value),
        value: cloneObservation(head ? head.postimage : value.value),
        correctionIds: cloneObservation(value.correctionIds || []),
        supersedesCorrectionId: head?.correctionId || null,
        chainValid: chain.length === 0 || heads.length === 1,
      });
      return;
    }
    for (const [key, child] of Object.entries(value)) visit(child, [...segments, key]);
  }
  visit(observation);
  return targets;
}

export function isCurationUnavailable(error) {
  return (
    error?.response?.status === 422 &&
    error?.response?.data?.detail?.code === 'curation_not_available'
  );
}
