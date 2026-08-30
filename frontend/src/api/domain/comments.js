// src/api/domain/comments.js — D.2 comments endpoints.
import { apiClient } from '../transport';

/**
 * List comments on a record.
 * @param {Object} opts
 * @param {string} opts.recordType
 * @param {string} opts.recordId - UUID string
 * @param {number} [opts.page=1]
 * @param {number} [opts.size=50]
 * @param {boolean} [opts.includeDeleted=false]
 * @param {('true'|'false'|null)} [opts.resolved=null]
 */
export const listComments = ({
  recordType,
  recordId,
  page = 1,
  size = 50,
  includeDeleted = false,
  resolved = null,
}) => {
  const params = {
    'filter[record_type]': recordType,
    'filter[record_id]': recordId,
    'page[number]': page,
    'page[size]': size,
  };
  if (includeDeleted) params.include = 'deleted';
  if (resolved !== null) params['filter[resolved]'] = resolved;
  return apiClient.get('/comments', { params });
};

export const getComment = (id, { includeDeleted = false } = {}) =>
  apiClient.get(`/comments/${id}`, {
    params: includeDeleted ? { include: 'deleted' } : {},
  });

export const createComment = ({
  recordType,
  recordId,
  bodyMarkdown,
  mentionUserIds = [],
  recordRevision,
  reviewRevisionId,
}) => {
  const body = {
    record_type: recordType,
    record_id: recordId,
    body_markdown: bodyMarkdown,
    mention_user_ids: mentionUserIds,
  };
  if (recordRevision !== undefined && recordRevision !== null) {
    body.record_revision = recordRevision;
  }
  if (reviewRevisionId !== undefined && reviewRevisionId !== null) {
    body.review_revision_id = reviewRevisionId;
  }
  return apiClient.post('/comments', body);
};

export const updateComment = (id, { bodyMarkdown, mentionUserIds = [] }) =>
  apiClient.patch(`/comments/${id}`, {
    body_markdown: bodyMarkdown,
    mention_user_ids: mentionUserIds,
  });

const issueActionBody = (request) => {
  if (!request) return undefined;
  const body = {
    record_revision: request.recordRevision,
    rationale: request.rationale,
  };
  if (request.disposition !== undefined && request.disposition !== null) {
    body.disposition = request.disposition;
  }
  return body;
};

export const resolveComment = (id, request) => {
  const body = issueActionBody(request);
  return body === undefined
    ? apiClient.post(`/comments/${id}/resolve`)
    : apiClient.post(`/comments/${id}/resolve`, body);
};
export const unresolveComment = (id, request) => {
  const body = issueActionBody(request);
  return body === undefined
    ? apiClient.post(`/comments/${id}/unresolve`)
    : apiClient.post(`/comments/${id}/unresolve`, body);
};
export const deleteComment = (id) => apiClient.delete(`/comments/${id}`);
export const listCommentEdits = (id) => apiClient.get(`/comments/${id}/edits`);

export const searchMentionableUsers = (q) => apiClient.get('/users/mentionable', { params: { q } });
