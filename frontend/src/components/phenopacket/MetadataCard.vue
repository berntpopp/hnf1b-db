<!-- src/components/phenopacket/MetadataCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon left color="grey-darken-2">
        mdi-information-outline
      </v-icon>
      Metadata
    </v-card-title>
    <v-card-text>
      <v-list density="compact">
        <v-list-item v-if="metaData.created">
          <v-list-item-title class="font-weight-bold">
            Created
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ formatDate(metaData.created) }}
            <span v-if="metaData.createdBy" class="ml-2 text-grey">
              by {{ metaData.createdBy }}
            </span>
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="metaData.phenopacketSchemaVersion">
          <v-list-item-title class="font-weight-bold">
            Schema Version
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ metaData.phenopacketSchemaVersion }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-divider v-if="metaData.externalReferences && metaData.externalReferences.length > 0" class="my-2" />

        <v-list-item v-if="metaData.externalReferences && metaData.externalReferences.length > 0">
          <v-list-item-title class="font-weight-bold mb-2">
            External References ({{ metaData.externalReferences.length }})
          </v-list-item-title>
          <v-list>
            <v-list-item
              v-for="(ref, index) in metaData.externalReferences"
              :key="index"
              density="compact"
            >
              <v-chip
                :href="ref.reference"
                target="_blank"
                color="blue"
                size="small"
                variant="flat"
                class="mr-2"
              >
                <v-icon left size="small">
                  mdi-open-in-new
                </v-icon>
                {{ ref.id }}
              </v-chip>
              <span class="text-caption">{{ ref.description }}</span>
            </v-list-item>
          </v-list>
        </v-list-item>

        <v-divider v-if="metaData.updates && metaData.updates.length > 0" class="my-2" />

        <v-list-item v-if="metaData.updates && metaData.updates.length > 0">
          <v-list-item-title class="font-weight-bold mb-2">
            Updates ({{ metaData.updates.length }})
          </v-list-item-title>
          <v-timeline density="compact" side="end">
            <v-timeline-item
              v-for="(update, index) in metaData.updates"
              :key="index"
              dot-color="blue"
              size="small"
            >
              <template #opposite>
                <span class="text-caption">{{ formatDate(update.timestamp) }}</span>
              </template>
              <div>
                <div class="font-weight-bold">{{ update.updatedBy }}</div>
                <div class="text-caption">{{ update.comment }}</div>
              </div>
            </v-timeline-item>
          </v-timeline>
        </v-list-item>

        <v-divider v-if="metaData.resources && metaData.resources.length > 0" class="my-2" />

        <v-list-item v-if="metaData.resources && metaData.resources.length > 0">
          <v-list-item-title class="font-weight-bold mb-2">
            Ontology Resources ({{ metaData.resources.length }})
          </v-list-item-title>
          <v-list>
            <v-list-item
              v-for="(resource, index) in metaData.resources"
              :key="index"
              density="compact"
            >
              <v-chip color="green" size="small" variant="flat" class="mr-2">
                {{ resource.namespacePrefix }}
              </v-chip>
              <span class="text-body-2">
                {{ resource.name }}
                <span v-if="resource.version" class="text-caption text-grey">
                  ({{ resource.version }})
                </span>
              </span>
            </v-list-item>
          </v-list>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'MetadataCard',
  props: {
    metaData: {
      type: Object,
      required: true,
    },
  },
  methods: {
    formatDate(dateString) {
      if (!dateString) return 'N/A';
      try {
        return new Date(dateString).toLocaleString();
      } catch {
        return dateString;
      }
    },
  },
};
</script>
