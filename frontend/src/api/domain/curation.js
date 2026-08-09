import { apiClient } from '../transport';

const recordPath = (phenopacketId) => `/phenopackets/${encodeURIComponent(phenopacketId)}`;
const revisionHeaders = (revision) => ({
  headers: { 'If-Match': `"${Number(revision)}"` },
});

export const getCurationLedger = (phenopacketId) =>
  apiClient.get(`${recordPath(phenopacketId)}/curation`);

export const previewCurationProjection = (phenopacketId, observation, config = undefined) =>
  apiClient.post(`${recordPath(phenopacketId)}/curation/preview`, { observation }, config);

export const saveReportObservation = (phenopacketId, observation, revision, changeReason) =>
  apiClient.patch(
    `${recordPath(phenopacketId)}/reports/${encodeURIComponent(observation.observationId)}`,
    { observation, changeReason },
    revisionHeaders(revision)
  );

export const appendCurationCorrection = (phenopacketId, correction, revision) =>
  apiClient.post(
    `${recordPath(phenopacketId)}/curation/corrections`,
    correction,
    revisionHeaders(revision)
  );

export const appendCurationResolution = (phenopacketId, resolution, revision) =>
  apiClient.post(
    `${recordPath(phenopacketId)}/curation/resolutions`,
    resolution,
    revisionHeaders(revision)
  );
