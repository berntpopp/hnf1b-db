import { describe, expect, it } from 'vitest';
import {
  STRUCTURE_START,
  STRUCTURE_END,
  isPositionInStructure,
  precomputedResidueDistance,
} from '@/utils/dnaDistanceCalculator';

describe('precomputedResidueDistance', () => {
  it('covers exactly the residues resolved in 2H8R', () => {
    for (let r = STRUCTURE_START - 5; r <= STRUCTURE_END + 5; r++) {
      expect(precomputedResidueDistance(r) !== null).toBe(isPositionInStructure(r));
    }
  });

  it('returns the distance with its category', () => {
    expect(precomputedResidueDistance(303)).toEqual({
      distance: 4.99189789655789,
      category: 'close',
    });
    expect(precomputedResidueDistance(90).category).toBe('far');
  });
});
