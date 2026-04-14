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

export const createComment = ({ recordType, recordId, bodyMarkdown, mentionUserIds = [] }) =>
  apiClient.post('/comments', {
    record_type: recordType,
    record_id: recordId,
    body_markdown: bodyMarkdown,
    mention_user_ids: mentionUserIds,
  });

export const updateComment = (id, { bodyMarkdown, mentionUserIds = [] }) =>
  apiClient.patch(`/comments/${id}`, {
    body_markdown: bodyMarkdown,
    mention_user_ids: mentionUserIds,
  });

export const resolveComment = (id) => apiClient.post(`/comments/${id}/resolve`);
export const unresolveComment = (id) => apiClient.post(`/comments/${id}/unresolve`);
export const deleteComment = (id) => apiClient.delete(`/comments/${id}`);
export const listCommentEdits = (id) => apiClient.get(`/comments/${id}/edits`);

export const searchMentionableUsers = (q) => apiClient.get('/users/mentionable', { params: { q } });
