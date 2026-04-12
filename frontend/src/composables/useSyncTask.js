/**
 * Composable for managing async sync-task polling state machines.
 *
 * Encapsulates the common pattern of: start a background sync task,
 * poll for status until it reaches a terminal state, then clean up.
 * Automatically clears the polling interval on component unmount.
 *
 * @param {Object} options
 * @param {Function} options.startFn - Async function that kicks off the sync task.
 *   Receives any args passed to start(). Must return { data: { task_id, status, items_to_process, ... } }.
 * @param {Function} options.statusFn - Async function that polls task status.
 *   Receives the task_id. Must return { data: { task_id, status, progress, processed, total, errors, ... } }.
 * @param {Function} [options.onComplete] - Called when the task reaches 'completed' status.
 * @param {Function} [options.onError] - Called with an error detail string on failure.
 * @param {number} [options.pollIntervalMs=2000] - Milliseconds between status polls.
 * @param {number} [options.clearTaskAfterMs=5000] - Milliseconds before clearing the task ref after terminal state.
 * @returns {{ task: Ref, inProgress: Ref<boolean>, start: Function, stop: Function }}
 *
 * @example
 * const { task, inProgress, start, stop } = useSyncTask({
 *   startFn: (force) => API.startPublicationSync(force),
 *   statusFn: (taskId) => API.getPublicationSyncStatus(taskId),
 *   onComplete: () => fetchStatus(),
 *   onError: (detail) => { error.value = detail; },
 * });
 */

import { ref, onUnmounted } from 'vue';

export function useSyncTask({
  startFn,
  statusFn,
  onComplete = () => {},
  onError = () => {},
  pollIntervalMs = 2000,
  clearTaskAfterMs = 5000,
}) {
  const task = ref(null);
  const inProgress = ref(false);
  let pollHandle = null;

  function _stopPolling() {
    if (pollHandle !== null) {
      clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  async function _poll() {
    try {
      const response = await statusFn(task.value?.task_id);
      task.value = response.data;
      const terminal = ['completed', 'failed'];
      if (terminal.includes(response.data.status)) {
        _stopPolling();
        inProgress.value = false;
        if (response.data.status === 'completed') {
          onComplete(response.data);
        } else {
          onError(response.data.message || 'sync task failed');
        }
        setTimeout(() => {
          task.value = null;
        }, clearTaskAfterMs);
      }
    } catch (err) {
      window.logService?.error('useSyncTask poll failed', { error: err.message });
    }
  }

  function _startPolling() {
    if (pollHandle !== null) return;
    pollHandle = setInterval(_poll, pollIntervalMs);
  }

  async function start(...startArgs) {
    try {
      inProgress.value = true;
      const response = await startFn(...startArgs);
      task.value = {
        task_id: response.data.task_id,
        status: response.data.status,
        progress: 0,
        processed: 0,
        total: response.data.items_to_process,
        errors: 0,
      };
      if (response.data.status === 'completed') {
        inProgress.value = false;
        task.value = null;
        onComplete(response.data);
      } else {
        _startPolling();
      }
    } catch (err) {
      inProgress.value = false;
      const detail = err.response?.data?.detail || err.message || 'sync failed';
      window.logService?.error('useSyncTask start failed', { error: detail });
      onError(detail);
    }
  }

  function stop() {
    _stopPolling();
  }

  onUnmounted(() => {
    _stopPolling();
  });

  return { task, inProgress, start, stop };
}
