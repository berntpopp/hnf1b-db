import { describe, it, expect } from 'vitest';
import { formatApiError, formatErrorDetail } from '@/utils/apiError';

describe('formatErrorDetail', () => {
  it('renders the backend validation_errors envelope, not "[object Object]"', () => {
    // The exact shape POST/PUT /phenopackets reject with
    // (backend/app/phenopackets/routers/crud.py).
    const detail = {
      validation_errors: [
        'Subject s1: Invalid HGVS g. notation: chr17-37739541-G-A',
        'Subject s1: Structural variant missing valid CNV notation',
      ],
    };
    const out = formatErrorDetail(detail);
    expect(out).toContain('Invalid HGVS g. notation');
    expect(out).toContain('Structural variant missing valid CNV notation');
    expect(out).not.toContain('[object Object]');
  });

  it('passes a string detail through untouched', () => {
    expect(formatErrorDetail('Phenopacket not found')).toBe('Phenopacket not found');
  });

  it('prefers detail.message for the {code, message} envelope', () => {
    expect(formatErrorDetail({ code: 'revision_mismatch', message: 'Revision 3 != 4' })).toBe(
      'Revision 3 != 4'
    );
  });

  it("renders FastAPI's own 422 array shape with the field path", () => {
    const out = formatErrorDetail([{ loc: ['body', 'subject', 'id'], msg: 'field required' }]);
    expect(out).toBe('body.subject.id: field required');
  });

  it('caps a long list but reports how many were withheld', () => {
    const validation_errors = Array.from({ length: 14 }, (_, i) => `error ${i}`);
    const out = formatErrorDetail({ validation_errors });
    expect(out).toContain('error 9');
    expect(out).not.toContain('error 10');
    expect(out).toContain('(+4 more)');
  });

  it('never degrades an unrecognised object to "[object Object]"', () => {
    expect(formatErrorDetail({ unexpected: 'shape' })).toBe('{"unexpected":"shape"}');
  });

  it('returns an empty string when there is nothing to say', () => {
    expect(formatErrorDetail(null)).toBe('');
    expect(formatErrorDetail(undefined)).toBe('');
    expect(formatErrorDetail({ validation_errors: [] })).toBe('{"validation_errors":[]}');
  });
});

describe('formatApiError', () => {
  it('prefers the response detail over the axios message', () => {
    const err = {
      message: 'Request failed with status code 400',
      response: { data: { detail: { validation_errors: ['subject.id: too short'] } } },
    };
    expect(formatApiError(err)).toBe('subject.id: too short');
  });

  it('falls back to the error message, then to the caller fallback', () => {
    expect(formatApiError({ message: 'Network Error' })).toBe('Network Error');
    expect(formatApiError({}, 'Unknown error')).toBe('Unknown error');
    expect(formatApiError(undefined, 'Unknown error')).toBe('Unknown error');
  });
});
