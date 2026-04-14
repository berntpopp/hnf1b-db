// src/composables/useComments.js — D.2 discussion tab state for one record.
import { ref, computed } from 'vue';
import {
  listComments,
  createComment,
  updateComment,
  resolveComment,
  unresolveComment,
  deleteComment,
} from '@/api/domain/comments';

/**
 * Comments composable for a single record.
 *
 * @param {string} recordType - e.g. "phenopacket"
 * @param {import('vue').Ref<string>} recordId - Reactive record UUID string.
 * @returns {Object} { comments, total, openCount, loading, error, load, post, edit, resolve, unresolve, remove, badgeLabel }
 */
export function useComments(recordType, recordId) {
  const comments = ref([]);
  const total = ref(0);
  const openCount = ref(0);
  const loading = ref(false);
  const error = ref(null);

  const load = async ({ page = 1, size = 50, includeDeleted = false } = {}) => {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await listComments({
        recordType,
        recordId: recordId.value,
        page,
        size,
        includeDeleted,
      });
      comments.value = data.data;
      total.value = data.meta.total;

      // Separately fetch unresolved count (lightweight — page size 1).
      const { data: openData } = await listComments({
        recordType,
        recordId: recordId.value,
        page: 1,
        size: 1,
        resolved: 'false',
      });
      openCount.value = openData.meta.total;
    } catch (e) {
      error.value = e;
      window.logService?.error?.('comments.load failed', {
        recordId: recordId.value,
        error: e.message,
      });
    } finally {
      loading.value = false;
    }
  };

  const post = async (bodyMarkdown, mentionUserIds = []) => {
    const { data } = await createComment({
      recordType,
      recordId: recordId.value,
      bodyMarkdown,
      mentionUserIds,
    });
    comments.value.push(data);
    total.value += 1;
    if (!data.resolved_at) openCount.value += 1;
    return data;
  };

  const edit = async (id, bodyMarkdown, mentionUserIds = []) => {
    const { data } = await updateComment(id, { bodyMarkdown, mentionUserIds });
    const i = comments.value.findIndex((c) => c.id === id);
    if (i !== -1) comments.value[i] = data;
    return data;
  };

  const resolve = async (id) => {
    const { data } = await resolveComment(id);
    const i = comments.value.findIndex((c) => c.id === id);
    if (i !== -1) comments.value[i] = data;
    openCount.value = Math.max(0, openCount.value - 1);
  };

  const unresolve = async (id) => {
    const { data } = await unresolveComment(id);
    const i = comments.value.findIndex((c) => c.id === id);
    if (i !== -1) comments.value[i] = data;
    openCount.value += 1;
  };

  const remove = async (id) => {
    await deleteComment(id);
    comments.value = comments.value.filter((c) => c.id !== id);
    total.value = Math.max(0, total.value - 1);
  };

  const badgeLabel = computed(() => {
    if (openCount.value > 0) return `Discussion (${total.value}, ${openCount.value} open)`;
    if (total.value > 0) return `Discussion (${total.value})`;
    return 'Discussion';
  });

  return {
    comments,
    total,
    openCount,
    loading,
    error,
    load,
    post,
    edit,
    resolve,
    unresolve,
    remove,
    badgeLabel,
  };
}
