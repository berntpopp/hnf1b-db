import { describe, it, expect } from 'vitest';
import { ref } from 'vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';

describe('useChartAccessibility', () => {
  it('returns role="img" plus stable labelledby/describedby IDs', () => {
    const summary = ref('Donut chart with 3 segments.');
    const { titleId, descId, ariaProps } = useChartAccessibility({
      chartName: 'Sex distribution',
      summary,
    });
    expect(ariaProps.role).toBe('img');
    expect(ariaProps['aria-labelledby']).toBe(titleId);
    expect(ariaProps['aria-describedby']).toBe(descId);
    expect(titleId).toMatch(/^chart-title-\d+$/);
    expect(descId).toMatch(/^chart-desc-\d+$/);
  });

  it('produces unique IDs across multiple instances', () => {
    const a = useChartAccessibility({ chartName: 'A', summary: ref('') });
    const b = useChartAccessibility({ chartName: 'B', summary: ref('') });
    expect(a.titleId).not.toBe(b.titleId);
    expect(a.descId).not.toBe(b.descId);
  });

  it('exposes the summary ref unchanged for template binding', () => {
    const summary = ref('first');
    const { description } = useChartAccessibility({ chartName: 'X', summary });
    expect(description.value).toBe('first');
    summary.value = 'second';
    expect(description.value).toBe('second');
  });
});
