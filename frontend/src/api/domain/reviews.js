import { apiClient } from '../transport';

const queueParamMap = {
  pageNumber: 'page[number]',
  pageSize: 'page[size]',
  state: 'filter[state]',
  owner: 'filter[owner]',
  eligibility: 'filter[eligibility]',
  issues: 'filter[issues]',
  q: 'q',
  sort: 'sort',
};

const definedParams = (params = {}) =>
  Object.fromEntries(
    Object.entries(queueParamMap)
      .filter(([key]) => params[key] !== undefined && params[key] !== null)
      .map(([key, alias]) => [alias, params[key]])
  );

export const getReviewQueue = (params = {}) =>
  apiClient.get('/phenopackets/review-queue', { params: definedParams(params) });

export const getReviewContext = (phenopacketId) =>
  apiClient.get(`/phenopackets/${encodeURIComponent(phenopacketId)}/review-context`);
