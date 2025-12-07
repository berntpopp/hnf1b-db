<!-- src/components/phenopacket/SubjectCard.vue -->
<template>
  <v-card outlined>
    <v-card-title :class="['text-subtitle-1', 'py-2', cardHeader.bgColor]">
      <v-icon left :color="cardHeader.iconColor" size="small">
        {{ cardHeader.icon }}
      </v-icon>
      {{ cardHeader.title }}
    </v-card-title>
    <v-card-text class="pa-3">
      <!-- Compact inline layout -->
      <div class="subject-grid">
        <!-- Subject ID -->
        <div class="subject-item">
          <span class="subject-label">Subject ID</span>
          <span class="subject-value font-weight-medium">{{ subject.id || 'N/A' }}</span>
        </div>

        <!-- Alternate IDs (if any) -->
        <div v-if="individualIdentifiers.length > 0 || reportIds.length > 0" class="subject-item">
          <span class="subject-label">
            Alternate ID{{ individualIdentifiers.length + reportIds.length > 1 ? 's' : '' }}
          </span>
          <div class="subject-value">
            <v-chip
              v-for="(identifier, index) in individualIdentifiers"
              :key="'name-' + index"
              size="x-small"
              class="mr-1"
              color="blue-lighten-4"
              variant="flat"
            >
              {{ identifier }}
            </v-chip>
            <v-chip
              v-for="(reportId, index) in reportIds"
              :key="'report-' + index"
              size="x-small"
              class="mr-1"
              color="grey-lighten-2"
              variant="flat"
            >
              {{ reportId }}
            </v-chip>
          </div>
        </div>

        <!-- Sex -->
        <div class="subject-item">
          <span class="subject-label">Sex</span>
          <span class="subject-value">
            <v-chip size="x-small" :color="getSexColor(subject.sex)" variant="flat">
              <v-icon size="x-small" class="mr-1">{{ getSexIcon(subject.sex) }}</v-icon>
              {{ formatSex(subject.sex) }}
            </v-chip>
          </span>
        </div>

        <!-- Karyotypic Sex (only if different from sex or informative) -->
        <div v-if="subject.karyotypicSex && showKaryotypicSex" class="subject-item">
          <span class="subject-label">Karyotype</span>
          <span class="subject-value">
            <v-chip size="x-small" color="purple-lighten-4" variant="flat">
              {{ subject.karyotypicSex }}
            </v-chip>
          </span>
        </div>

        <!-- Age at Last Encounter -->
        <div v-if="age" class="subject-item">
          <span class="subject-label">Age</span>
          <span class="subject-value">
            <v-chip size="x-small" color="amber-lighten-4" variant="flat">
              <v-icon size="x-small" class="mr-1">mdi-calendar-clock</v-icon>
              {{ age }}
            </v-chip>
          </span>
        </div>

        <!-- Taxonomy (usually Homo sapiens, show only if different) -->
        <div v-if="subject.taxonomy && !isHomoSapiens" class="subject-item">
          <span class="subject-label">Taxonomy</span>
          <span class="subject-value text-body-2">
            {{ subject.taxonomy.label || subject.taxonomy.id }}
          </span>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import { CARD_HEADERS, SEX_COLORS } from '@/utils/cardStyles';

export default {
  name: 'SubjectCard',
  props: {
    subject: {
      type: Object,
      required: true,
    },
  },
  computed: {
    cardHeader() {
      return CARD_HEADERS.subject;
    },
    individualIdentifiers() {
      const altIds = this.subject.alternateIds || [];
      return altIds.filter((id) => !/^\d+$/.test(id));
    },

    reportIds() {
      const altIds = this.subject.alternateIds || [];
      return altIds.filter((id) => /^\d+$/.test(id));
    },

    age() {
      const timeAtLastEncounter = this.subject.timeAtLastEncounter;
      if (timeAtLastEncounter?.age?.iso8601duration) {
        return this.formatISO8601Duration(timeAtLastEncounter.age.iso8601duration);
      }
      return null;
    },

    showKaryotypicSex() {
      // Show karyotypic sex if it's informative (not just XX/XY matching sex)
      const karyotype = this.subject.karyotypicSex;
      if (!karyotype) return false;

      // Always show non-standard karyotypes
      if (!['XX', 'XY', 'UNKNOWN_KARYOTYPE'].includes(karyotype)) return true;

      // Show if there's a mismatch with phenotypic sex
      const sex = this.subject.sex;
      if (sex === 'MALE' && karyotype !== 'XY') return true;
      if (sex === 'FEMALE' && karyotype !== 'XX') return true;

      return false;
    },

    isHomoSapiens() {
      const taxonomy = this.subject.taxonomy;
      if (!taxonomy) return true; // Assume human if not specified
      const label = (taxonomy.label || taxonomy.id || '').toLowerCase();
      return label.includes('homo') || label.includes('sapiens') || label.includes('human');
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
      return SEX_COLORS[sex] || SEX_COLORS.UNKNOWN_SEX;
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
      const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?/;
      const matches = duration.match(regex);
      if (!matches) return duration;

      const parts = [];
      if (matches[1]) parts.push(`${matches[1]}y`);
      if (matches[2]) parts.push(`${matches[2]}m`);
      if (matches[3]) parts.push(`${matches[3]}d`);

      return parts.join(' ') || duration;
    },
  },
};
</script>

<style scoped>
/**
 * Typography tokens applied via CSS custom properties.
 * Values sourced from cardStyles.js TYPOGRAPHY and COLORS.
 */
.subject-grid {
  /* Typography tokens - consistent across all phenopacket cards */
  --font-size-sm: 11px;
  --font-size-md: 13px;

  /* Color tokens */
  --color-text-primary: rgba(0, 0, 0, 0.87);
  --color-text-secondary: rgba(0, 0, 0, 0.5);

  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px 16px;
}

.subject-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.subject-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-secondary);
}

.subject-value {
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
}
</style>
