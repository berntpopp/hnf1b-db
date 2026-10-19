import { describe, expect, it } from 'vitest';

import { sprintf, vsprintf } from '@/utils/sprintf';

describe('sprintf utility (GHSA-hp3w-g68c-fv3c mitigation)', () => {
  it('formats standard NGL PDB/MDL records and numeric specifiers', () => {
    expect(sprintf('TITLE %-10s', '2H8R')).toBe('TITLE 2H8R      ');
    expect(sprintf('MODEL     %4d', 1)).toBe('MODEL        1');
    expect(sprintf('%.2f', 3.14159)).toBe('3.14');
    expect(vsprintf('%s=%d', ['atoms', 42])).toBe('atoms=42');
  });

  it('clamps unbounded precision specifiers instead of throwing RangeError', () => {
    expect(() => sprintf('%.9999f', 1.25)).not.toThrow();
    expect(() => sprintf('%.9999e', 1.25)).not.toThrow();
    expect(() => sprintf('%.9999g', 1.25)).not.toThrow();
    expect(sprintf('%.500f', 1.5).startsWith('1.500000')).toBe(true);
  });
});
