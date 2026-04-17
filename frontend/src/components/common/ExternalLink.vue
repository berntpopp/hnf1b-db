<template>
  <a
    :href="href"
    target="_blank"
    rel="noopener noreferrer"
    :aria-label="ariaLabel || undefined"
    class="external-link"
  >
    <slot />
    <v-icon
      v-if="showIcon"
      class="external-link__icon mdi-open-in-new"
      size="x-small"
      aria-hidden="true"
    >
      mdi-open-in-new
    </v-icon>
    <span class="sr-only">(opens in new tab)</span>
  </a>
</template>

<script setup>
defineProps({
  href: { type: String, required: true },
  ariaLabel: { type: String, default: '' },
  showIcon: { type: Boolean, default: true },
});
</script>

<style scoped>
.external-link {
  color: inherit;
  text-decoration: none;
}
.external-link:hover {
  text-decoration: underline;
}
.external-link__icon {
  margin-left: 4px;
  vertical-align: -2px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
