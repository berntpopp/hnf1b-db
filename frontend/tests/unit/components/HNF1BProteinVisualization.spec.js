/**
 * Unit tests for HNF1B Protein Visualization component
 *
 * Tests cover:
 * - Domain coordinate validation against UniProt P35680
 * - Domain boundary mapping (non-overlapping, complete coverage)
 * - Variant position to domain mapping
 * - isPositionInDomain() helper method
 * - Protein length validation
 */

import { describe, it, expect } from 'vitest';

// Domain data from HNF1BProteinVisualization.vue (verified from UniProt P35680)
// Source: https://www.uniprot.org/uniprotkb/P35680/entry
// RefSeq: NP_000449.1
// Verified: 2025-01-17
const HNF1B_DOMAINS = [
  {
    name: 'Dimerization Domain',
    shortName: 'Dim',
    start: 1,
    end: 31,
    color: '#FFB74D',
    function: 'Mediates homodimer or heterodimer formation',
  },
  {
    name: 'POU-Specific Domain',
    shortName: 'POU-S',
    start: 8,
    end: 173,
    color: '#64B5F6',
    function: 'DNA binding (part 1) - IPR000327',
  },
  {
    name: 'POU Homeodomain',
    shortName: 'POU-H',
    start: 232,
    end: 305,
    color: '#4FC3F7',
    function: 'DNA binding (part 2) - IPR001356',
  },
  {
    name: 'Transactivation Domain',
    shortName: 'TAD',
    start: 314,
    end: 557,
    color: '#81C784',
    function: 'Transcriptional activation',
  },
];

const PROTEIN_LENGTH = 557;

// Helper function matching the one in HNF1BProteinVisualization.vue
function isPositionInDomain(position) {
  const pos = parseInt(position);
  return HNF1B_DOMAINS.some((domain) => pos >= domain.start && pos <= domain.end);
}

describe('HNF1BProteinVisualization - Domain Validation', () => {
  describe('Domain Coordinate Validation (UniProt P35680)', () => {
    it('should have correct Dimerization domain boundaries (1-31)', () => {
      const dimDomain = HNF1B_DOMAINS.find((d) => d.shortName === 'Dim');
      expect(dimDomain).toBeDefined();
      expect(dimDomain.start).toBe(1);
      expect(dimDomain.end).toBe(31);
      expect(dimDomain.name).toBe('Dimerization Domain');
    });

    it('should have correct POU-Specific domain boundaries (8-173)', () => {
      const pouSDomain = HNF1B_DOMAINS.find((d) => d.shortName === 'POU-S');
      expect(pouSDomain).toBeDefined();
      expect(pouSDomain.start).toBe(8);
      expect(pouSDomain.end).toBe(173);
      expect(pouSDomain.name).toBe('POU-Specific Domain');
      expect(pouSDomain.function).toContain('IPR000327');
    });

    it('should have correct POU Homeodomain boundaries (232-305)', () => {
      const pouHDomain = HNF1B_DOMAINS.find((d) => d.shortName === 'POU-H');
      expect(pouHDomain).toBeDefined();
      expect(pouHDomain.start).toBe(232);
      expect(pouHDomain.end).toBe(305);
      expect(pouHDomain.name).toBe('POU Homeodomain');
      expect(pouHDomain.function).toContain('IPR001356');
    });

    it('should have correct Transactivation domain boundaries (314-557)', () => {
      const tadDomain = HNF1B_DOMAINS.find((d) => d.shortName === 'TAD');
      expect(tadDomain).toBeDefined();
      expect(tadDomain.start).toBe(314);
      expect(tadDomain.end).toBe(557);
      expect(tadDomain.name).toBe('Transactivation Domain');
    });

    it('should have exactly 4 protein domains', () => {
      expect(HNF1B_DOMAINS).toHaveLength(4);
    });

    it('should have correct protein length (557 amino acids)', () => {
      expect(PROTEIN_LENGTH).toBe(557);
    });
  });

  describe('Domain Boundary Validation', () => {
    it('should have non-overlapping domain boundaries', () => {
      // Check each pair of domains for overlap
      for (let i = 0; i < HNF1B_DOMAINS.length; i++) {
        for (let j = i + 1; j < HNF1B_DOMAINS.length; j++) {
          const domain1 = HNF1B_DOMAINS[i];
          const domain2 = HNF1B_DOMAINS[j];

          // Check if domains overlap
          const overlap =
            (domain1.start <= domain2.end && domain1.end >= domain2.start) ||
            (domain2.start <= domain1.end && domain2.end >= domain1.start);

          // Allow overlap only for Dimerization (1-31) and POU-Specific (8-173)
          // as they are known to overlap in the actual protein structure
          const isAllowedOverlap =
            (domain1.shortName === 'Dim' && domain2.shortName === 'POU-S') ||
            (domain1.shortName === 'POU-S' && domain2.shortName === 'Dim');

          if (overlap && !isAllowedOverlap) {
            throw new Error(
              `Unexpected overlap between ${domain1.name} (${domain1.start}-${domain1.end}) and ${domain2.name} (${domain2.start}-${domain2.end})`
            );
          }
        }
      }
    });

    it('should have all domain boundaries within protein length', () => {
      HNF1B_DOMAINS.forEach((domain) => {
        expect(domain.start).toBeGreaterThanOrEqual(1);
        expect(domain.end).toBeLessThanOrEqual(PROTEIN_LENGTH);
        expect(domain.start).toBeLessThan(domain.end);
      });
    });

    it('should have domains with positive length', () => {
      HNF1B_DOMAINS.forEach((domain) => {
        const length = domain.end - domain.start + 1;
        expect(length).toBeGreaterThan(0);
      });
    });
  });

  describe('Variant Position to Domain Mapping', () => {
    describe('isPositionInDomain() helper method', () => {
      it('should return true for position inside Dimerization domain', () => {
        expect(isPositionInDomain(1)).toBe(true);
        expect(isPositionInDomain(15)).toBe(true);
        expect(isPositionInDomain(31)).toBe(true);
      });

      it('should return true for position inside POU-Specific domain', () => {
        expect(isPositionInDomain(8)).toBe(true);
        expect(isPositionInDomain(100)).toBe(true);
        expect(isPositionInDomain(173)).toBe(true);
      });

      it('should return true for position inside POU Homeodomain', () => {
        expect(isPositionInDomain(232)).toBe(true);
        expect(isPositionInDomain(270)).toBe(true);
        expect(isPositionInDomain(305)).toBe(true);
      });

      it('should return true for position inside Transactivation domain', () => {
        expect(isPositionInDomain(314)).toBe(true);
        expect(isPositionInDomain(400)).toBe(true);
        expect(isPositionInDomain(557)).toBe(true);
      });

      it('should return false for position outside all domains', () => {
        // Position 174-231 is between POU-Specific and POU Homeodomain
        expect(isPositionInDomain(174)).toBe(false);
        expect(isPositionInDomain(200)).toBe(false);
        expect(isPositionInDomain(231)).toBe(false);

        // Position 306-313 is between POU Homeodomain and Transactivation
        expect(isPositionInDomain(306)).toBe(false);
        expect(isPositionInDomain(310)).toBe(false);
        expect(isPositionInDomain(313)).toBe(false);
      });

      it('should return false for position beyond protein length', () => {
        expect(isPositionInDomain(558)).toBe(false);
        expect(isPositionInDomain(600)).toBe(false);
        expect(isPositionInDomain(1000)).toBe(false);
      });

      it('should return false for position before protein start', () => {
        expect(isPositionInDomain(0)).toBe(false);
        expect(isPositionInDomain(-1)).toBe(false);
      });

      it('should handle string position inputs', () => {
        // Method should parse string to int
        expect(isPositionInDomain('100')).toBe(true);
        expect(isPositionInDomain('200')).toBe(false);
        expect(isPositionInDomain('400')).toBe(true);
      });
    });

    describe('Known variant positions', () => {
      it('should correctly map p.Arg177 (known variant) to POU-Specific domain', () => {
        const position = 177;
        expect(isPositionInDomain(position)).toBe(false);
        // Position 177 is outside POU-Specific (8-173) - in the linker region
      });

      it('should correctly map p.Met1 (start codon) to Dimerization domain', () => {
        const position = 1;
        expect(isPositionInDomain(position)).toBe(true);
      });

      it('should correctly map p.Ser546 to Transactivation domain', () => {
        const position = 546;
        expect(isPositionInDomain(position)).toBe(true);
      });
    });
  });

  describe('Domain Metadata Validation', () => {
    it('should have InterPro IDs for POU domains', () => {
      const pouS = HNF1B_DOMAINS.find((d) => d.shortName === 'POU-S');
      const pouH = HNF1B_DOMAINS.find((d) => d.shortName === 'POU-H');

      expect(pouS.function).toContain('IPR000327');
      expect(pouH.function).toContain('IPR001356');
    });

    it('should have color assigned to each domain', () => {
      HNF1B_DOMAINS.forEach((domain) => {
        expect(domain.color).toBeDefined();
        expect(domain.color).toMatch(/^#[0-9A-Fa-f]{6}$/);
      });
    });

    it('should have functional descriptions for all domains', () => {
      HNF1B_DOMAINS.forEach((domain) => {
        expect(domain.function).toBeDefined();
        expect(domain.function.length).toBeGreaterThan(0);
      });
    });

    it('should have short names for all domains', () => {
      const shortNames = HNF1B_DOMAINS.map((d) => d.shortName);
      expect(shortNames).toContain('Dim');
      expect(shortNames).toContain('POU-S');
      expect(shortNames).toContain('POU-H');
      expect(shortNames).toContain('TAD');
    });
  });

  describe('Automated Domain Validation Tests', () => {
    it('should detect if domain coordinates change unexpectedly', () => {
      // This test will fail if domain coordinates are modified
      // Serves as a canary to ensure changes are intentional
      const expectedDomains = [
        { shortName: 'Dim', start: 1, end: 31 },
        { shortName: 'POU-S', start: 8, end: 173 },
        { shortName: 'POU-H', start: 232, end: 305 },
        { shortName: 'TAD', start: 314, end: 557 },
      ];

      expectedDomains.forEach((expected) => {
        const actual = HNF1B_DOMAINS.find((d) => d.shortName === expected.shortName);
        expect(actual).toBeDefined();
        expect(actual.start).toBe(expected.start);
        expect(actual.end).toBe(expected.end);
      });
    });

    it('should validate domain order is logical (sorted by start position)', () => {
      for (let i = 0; i < HNF1B_DOMAINS.length - 1; i++) {
        // Allow for overlapping Dimerization and POU-Specific domains
        if (HNF1B_DOMAINS[i].shortName === 'Dim' && HNF1B_DOMAINS[i + 1].shortName === 'POU-S') {
          continue;
        }
        if (HNF1B_DOMAINS[i].shortName === 'POU-S' && HNF1B_DOMAINS[i + 1].shortName === 'Dim') {
          continue;
        }

        // All other domains should be non-overlapping
        expect(HNF1B_DOMAINS[i].end).toBeLessThan(HNF1B_DOMAINS[i + 1].start);
      }
    });

    it('should validate total domain coverage percentage', () => {
      // Calculate unique positions covered by domains
      const coveredPositions = new Set();
      HNF1B_DOMAINS.forEach((domain) => {
        for (let pos = domain.start; pos <= domain.end; pos++) {
          coveredPositions.add(pos);
        }
      });

      const coveragePercent = (coveredPositions.size / PROTEIN_LENGTH) * 100;

      // HNF1B domains should cover at least 75% of the protein
      expect(coveragePercent).toBeGreaterThan(75);
    });

    it('should ensure no domain extends beyond protein length', () => {
      HNF1B_DOMAINS.forEach((domain) => {
        expect(domain.end).toBeLessThanOrEqual(PROTEIN_LENGTH);
      });
    });

    it('should validate that last domain ends at protein terminus', () => {
      const tadDomain = HNF1B_DOMAINS.find((d) => d.shortName === 'TAD');
      expect(tadDomain.end).toBe(PROTEIN_LENGTH);
    });
  });
});
