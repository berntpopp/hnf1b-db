<template>
  <v-container class="py-6">
    <section aria-labelledby="review-queue-title" aria-busy="true">
      <div class="d-flex align-center ga-3">
        <v-progress-circular indeterminate color="primary" size="24" />
        <div>
          <h1 id="review-queue-title" class="text-h5 mb-1">Review Queue</h1>
          <p class="text-body-2 text-medium-emphasis mb-0">
            Loading records ready for curator review.
          </p>
        </div>
      </div>
    </section>
  </v-container>
</template>

<script setup></script>

<style scoped></style>
