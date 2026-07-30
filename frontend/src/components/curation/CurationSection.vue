<!-- src/components/curation/CurationSection.vue -->
<!--
  Collapsible section wrapper for the curation console (curation console
  design spec §2, §5; plan Task 3). Each console section (Case, Variant,
  Classification, Phenotypes, Age & Onset, Provenance & Notes) is one of
  these, showing a title, a `filled/total` completeness badge, and toggling
  its content.

  State ownership: this component owns its own expanded/collapsed state
  (persisted to localStorage) rather than being a purely parent-controlled
  v-model. A curator navigating from CompletenessRail needs a section to
  force-open even if it's currently collapsed; the parent does that by
  holding a template ref to this component and calling the exposed
  `expand()` method, rather than the parent owning a big reactive
  "expandedSections" map that this component would just seed/persist.
-->
<template>
  <v-card :id="`curation-section-${id}`" variant="outlined" class="curation-section mb-4">
    <button
      type="button"
      class="curation-section__header"
      :aria-expanded="isOpen ? 'true' : 'false'"
      :aria-controls="contentId"
      @click="toggle"
    >
      <v-icon
        class="curation-section__chevron"
        :class="{ 'curation-section__chevron--open': isOpen }"
        size="small"
        aria-hidden="true"
      >
        mdi-chevron-down
      </v-icon>
      <span class="curation-section__title text-subtitle-1 font-weight-medium">{{ title }}</span>
      <v-spacer />
      <v-chip size="small" color="primary" variant="tonal" class="curation-section__badge">
        {{ filled }}/{{ total }}
      </v-chip>
    </button>

    <v-expand-transition v-if="!prefersReducedMotion">
      <div v-show="isOpen" :id="contentId" class="curation-section__content">
        <v-card-text>
          <slot />
        </v-card-text>
      </div>
    </v-expand-transition>
    <div v-else v-show="isOpen" :id="contentId" class="curation-section__content">
      <v-card-text>
        <slot />
      </v-card-text>
    </div>
  </v-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { usePrefersReducedMotion } from '@/composables/useAccessibility';

// Single JSON object mapping sectionId -> expanded (boolean), so a curator
// returning to a case resumes with the same sections open/closed.
const STORAGE_KEY = 'hnf1b-curation-section-state';

const props = defineProps({
  id: { type: String, required: true },
  title: { type: String, default: '' },
  filled: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue']);

const prefersReducedMotion = usePrefersReducedMotion();
const isOpen = ref(props.modelValue);
const contentId = computed(() => `curation-section-${props.id}-content`);

function readStoredState() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    // Corrupt JSON or localStorage unavailable (private mode, quota) --
    // fall back to "no stored state", never throw during render.
    return {};
  }
}

function persistState(nextOpen) {
  try {
    const state = readStoredState();
    state[props.id] = nextOpen;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage unavailable -- expand state just won't survive a reload.
  }
}

onMounted(() => {
  const stored = readStoredState();
  if (Object.prototype.hasOwnProperty.call(stored, props.id)) {
    const storedOpen = !!stored[props.id];
    if (storedOpen !== isOpen.value) {
      isOpen.value = storedOpen;
      emit('update:modelValue', storedOpen);
    }
  }
});

// A parent that explicitly drives modelValue (e.g. resetting a form) is
// still respected after mount; this does not fight the localStorage-seeded
// initial value above because that only runs once, before any parent-driven
// change would arrive.
watch(
  () => props.modelValue,
  (next) => {
    if (next !== isOpen.value) {
      isOpen.value = next;
    }
  }
);

function setOpen(next) {
  if (next === isOpen.value) return;
  isOpen.value = next;
  emit('update:modelValue', next);
  persistState(next);
}

function toggle() {
  setOpen(!isOpen.value);
}

function expand() {
  setOpen(true);
}

defineExpose({ expand });
</script>

<style scoped>
.curation-section__header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 12px 16px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}

.curation-section__header:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: -2px;
}

.curation-section__chevron {
  transition: transform 0.2s ease;
}

.curation-section__chevron--open {
  transform: rotate(180deg);
}

@media (prefers-reduced-motion: reduce) {
  .curation-section__chevron {
    transition: none;
  }
}
</style>
