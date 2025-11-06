<!-- src/components/phenopacket/SubjectCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1 py-2 bg-blue-lighten-5">
      <v-icon left color="primary" size="small"> mdi-account </v-icon>
      Subject Information
    </v-card-title>
    <v-card-text class="pa-2">
      <v-list density="compact">
        <v-list-item>
          <v-list-item-title class="font-weight-bold"> Subject ID </v-list-item-title>
          <v-list-item-subtitle>{{ subject.id || 'N/A' }}</v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="subject.alternateIds && subject.alternateIds.length > 0">
          <v-list-item-title class="font-weight-bold">
            Individual Identifier{{ subject.alternateIds.length > 1 ? 's' : '' }}
          </v-list-item-title>
          <v-list-item-subtitle>
            <v-chip
              v-for="(altId, index) in subject.alternateIds"
              :key="index"
              size="small"
              class="mr-1 mb-1 font-weight-medium"
              color="blue-lighten-4"
              variant="flat"
            >
              {{ altId }}
            </v-chip>
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold"> Sex </v-list-item-title>
          <v-list-item-subtitle>
            <v-icon small :color="getSexColor(subject.sex)" class="mr-1">
              {{ getSexIcon(subject.sex) }}
            </v-icon>
            {{ formatSex(subject.sex) }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="subject.karyotypicSex">
          <v-list-item-title class="font-weight-bold"> Karyotypic Sex </v-list-item-title>
          <v-list-item-subtitle>{{ subject.karyotypicSex }}</v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="age">
          <v-list-item-title class="font-weight-bold"> Age at Last Encounter </v-list-item-title>
          <v-list-item-subtitle>{{ age }}</v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="subject.taxonomy">
          <v-list-item-title class="font-weight-bold"> Taxonomy </v-list-item-title>
          <v-list-item-subtitle>
            {{ subject.taxonomy.label || subject.taxonomy.id }}
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'SubjectCard',
  props: {
    subject: {
      type: Object,
      required: true,
    },
  },
  computed: {
    age() {
      const timeAtLastEncounter = this.subject.timeAtLastEncounter;
      if (timeAtLastEncounter?.age?.iso8601duration) {
        return this.formatISO8601Duration(timeAtLastEncounter.age.iso8601duration);
      }
      return null;
    },
  },
  methods: {
    getSexIcon(sex) {
      const icons = {
        MALE: 'mdi-gender-male',
        FEMALE: 'mdi-gender-female',
        OTHER_SEX: 'mdi-gender-non-binary',
        UNKNOWN_SEX: 'mdi-help-circle',
      };
      return icons[sex] || 'mdi-help-circle';
    },

    getSexColor(sex) {
      const colors = {
        MALE: 'blue',
        FEMALE: 'pink',
        OTHER_SEX: 'purple',
        UNKNOWN_SEX: 'grey',
      };
      return colors[sex] || 'grey';
    },

    formatSex(sex) {
      const labels = {
        MALE: 'Male',
        FEMALE: 'Female',
        OTHER_SEX: 'Other',
        UNKNOWN_SEX: 'Unknown',
      };
      return labels[sex] || sex;
    },

    formatISO8601Duration(duration) {
      // Parse ISO8601 duration (e.g., "P45Y3M" = 45 years 3 months)
      const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?/;
      const matches = duration.match(regex);
      if (!matches) return duration;

      const parts = [];
      if (matches[1]) parts.push(`${matches[1]} year${matches[1] > 1 ? 's' : ''}`);
      if (matches[2]) parts.push(`${matches[2]} month${matches[2] > 1 ? 's' : ''}`);
      if (matches[3]) parts.push(`${matches[3]} day${matches[3] > 1 ? 's' : ''}`);

      return parts.join(', ') || duration;
    },
  },
};
</script>
