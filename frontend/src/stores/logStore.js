/**
 * Pinia Store for Log Viewer UI State
 * Manages log storage, filtering, and viewer visibility
 */

import { defineStore } from 'pinia';

export const useLogStore = defineStore('logs', {
  state: () => ({
    logs: [],
    maxLogs: 1000,
    isViewerOpen: false,
    minDisplayLevel: 1, // Default: INFO (0=DEBUG, 1=INFO, 2=WARN, 3=ERROR)

    // Filter state
    filters: {
      search: '',
      level: null, // null | 'DEBUG' | 'INFO' | 'WARN' | 'ERROR'
      component: null,
    },
  }),

  getters: {
    /**
     * Get filtered logs based on current filters AND minimum display level
     */
    filteredLogs: (state) => {
      let filtered = [...state.logs];

      // Filter by minimum display level FIRST
      filtered = filtered.filter((log) => log.levelValue >= state.minDisplayLevel);

      // Filter by specific level (user filter)
      if (state.filters.level) {
        filtered = filtered.filter((log) => log.level === state.filters.level);
      }

      // Filter by search text
      if (state.filters.search) {
        const search = state.filters.search.toLowerCase();
        filtered = filtered.filter(
          (log) =>
            log.message.toLowerCase().includes(search) ||
            JSON.stringify(log.context).toLowerCase().includes(search)
        );
      }

      // Filter by component
      if (state.filters.component) {
        filtered = filtered.filter((log) => log.component === state.filters.component);
      }

      return filtered;
    },

    /**
     * Get unique component names from logs
     */
    componentNames: (state) => {
      const names = new Set(state.logs.map((log) => log.component));
      return Array.from(names).sort();
    },

    /**
     * Get log count by level
     */
    logCountByLevel: (state) => {
      return state.logs.reduce((acc, log) => {
        acc[log.level] = (acc[log.level] || 0) + 1;
        return acc;
      }, {});
    },
  },

  actions: {
    /**
     * Add log entry (circular buffer)
     */
    addLog(log) {
      // ✅ Immutable pattern for Vue reactivity
      if (this.logs.length >= this.maxLogs) {
        this.logs = [...this.logs.slice(-(this.maxLogs - 1)), log];
      } else {
        this.logs = [...this.logs, log];
      }
    },

    /**
     * Clear all logs
     */
    clearLogs() {
      this.logs = [];
    },

    /**
     * Toggle log viewer visibility
     */
    toggleViewer() {
      this.isViewerOpen = !this.isViewerOpen;
    },

    /**
     * Set filter values
     */
    setFilter(filterName, value) {
      this.filters[filterName] = value;
    },

    /**
     * Reset all filters
     */
    resetFilters() {
      this.filters = {
        search: '',
        level: null,
        component: null,
      };
    },

    /**
     * Export logs as JSON
     */
    exportLogs() {
      const blob = new Blob([JSON.stringify(this.logs, null, 2)], {
        type: 'application/json',
      });

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

      link.href = url;
      link.download = `logs-${timestamp}.json`;
      link.click();

      URL.revokeObjectURL(url);
    },

    /**
     * Set minimum display level (0=DEBUG, 1=INFO, 2=WARN, 3=ERROR)
     */
    setMinLevel(levelValue) {
      this.minDisplayLevel = levelValue;
    },
  },
});
