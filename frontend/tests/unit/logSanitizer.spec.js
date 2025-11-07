import { describe, it, expect } from 'vitest';
import { sanitizeLogData, containsSensitiveData } from '@/utils/logSanitizer';

describe('logSanitizer', () => {
  describe('sanitizeLogData', () => {
    it('should redact HPO terms', () => {
      const result = sanitizeLogData('Found HP:0001234 in record');
      expect(result.message).toBe('Found [HPO_TERM] in record');
    });

    it('should redact multiple HPO terms', () => {
      const result = sanitizeLogData('HP:0001234 and HP:0005678');
      expect(result.message).toBe('[HPO_TERM] and [HPO_TERM]');
    });

    it('should redact variants', () => {
      const result = sanitizeLogData('Variant NM_000123.4:c.123A>G detected');
      expect(result.message).toContain('[VARIANT]');
    });

    it('should redact MONDO disease codes', () => {
      const result = sanitizeLogData('Disease MONDO:0012345 found');
      expect(result.message).toBe('Disease [DISEASE] found');
    });

    it('should redact email addresses', () => {
      const result = sanitizeLogData('User: test@example.com logged in');
      expect(result.message).toBe('User: [EMAIL] logged in');
    });

    it('should redact JWT tokens', () => {
      const result = sanitizeLogData('Auth: Bearer eyJhbGciOiJIUzI1NiIs');
      expect(result.message).toBe('Auth: Bearer [TOKEN]');
    });

    it('should redact DNA sequences', () => {
      const result = sanitizeLogData('Sequence: ATCGATCGATCG found');
      expect(result.message).toBe('Sequence: [DNA_SEQUENCE] found');
    });

    it('should redact RNA sequences', () => {
      const result = sanitizeLogData('RNA: AUCGAUCGAUCG present');
      expect(result.message).toBe('RNA: [RNA_SEQUENCE] present');
    });

    it('should redact subject IDs', () => {
      const result = sanitizeLogData('Subject HNF1B-123 updated');
      expect(result.message).toBe('Subject [SUBJECT_ID] updated');
    });

    it('should redact API keys', () => {
      const result = sanitizeLogData('Key: abcdefghijklmnopqrstuvwxyz123456 used');
      expect(result.message).toContain('[API_KEY]');
    });

    it('should handle context object redaction', () => {
      const result = sanitizeLogData('User data', {
        email: 'user@test.com',
        hpo: 'HP:0001234',
        variant: 'NM_000123.4:c.456T>C',
      });

      expect(result.context.email).toBe('[EMAIL]');
      expect(result.context.hpo).toBe('[HPO_TERM]');
      expect(result.context.variant).toBe('[VARIANT]');
    });

    it('should handle nested context objects', () => {
      const result = sanitizeLogData('Complex data', {
        user: {
          contact: 'admin@test.com',
        },
        phenotype: {
          term: 'HP:0001234',
        },
      });

      expect(result.context.user.contact).toBe('[EMAIL]');
      expect(result.context.phenotype.term).toBe('[HPO_TERM]');
    });

    it('should preserve non-sensitive data', () => {
      const result = sanitizeLogData('Normal log message', { count: 123 });
      expect(result.message).toBe('Normal log message');
      expect(result.context.count).toBe(123);
    });

    it('should handle empty context', () => {
      const result = sanitizeLogData('Message only');
      expect(result.message).toBe('Message only');
      expect(result.context).toEqual({});
    });

    it('should handle multiple pattern types in one message', () => {
      const result = sanitizeLogData(
        'User test@example.com has HP:0001234 with variant NM_000123.4:c.789G>A'
      );
      expect(result.message).toContain('[EMAIL]');
      expect(result.message).toContain('[HPO_TERM]');
      expect(result.message).toContain('[VARIANT]');
    });
  });

  describe('containsSensitiveData', () => {
    it('should detect HPO terms', () => {
      expect(containsSensitiveData('HP:0001234')).toBe(true);
    });

    it('should detect emails', () => {
      expect(containsSensitiveData('test@example.com')).toBe(true);
    });

    it('should detect variants', () => {
      expect(containsSensitiveData('NM_000123.4:c.123A>G')).toBe(true);
    });

    it('should detect DNA sequences', () => {
      expect(containsSensitiveData('ATCGATCGATCG')).toBe(true);
    });

    it('should detect subject IDs', () => {
      expect(containsSensitiveData('HNF1B-123')).toBe(true);
    });

    it('should detect JWT tokens', () => {
      expect(containsSensitiveData('Bearer eyJhbGciOiJIUzI1NiIs')).toBe(true);
    });

    it('should return false for safe data', () => {
      expect(containsSensitiveData('Normal text')).toBe(false);
      expect(containsSensitiveData({ count: 123, name: 'Test' })).toBe(false);
    });

    it('should detect sensitive data in objects', () => {
      expect(containsSensitiveData({ email: 'test@example.com' })).toBe(true);
      expect(containsSensitiveData({ hpo: 'HP:0001234' })).toBe(true);
    });

    it('should detect sensitive data in nested objects', () => {
      const data = {
        user: {
          contact: 'admin@test.com',
        },
      };
      expect(containsSensitiveData(data)).toBe(true);
    });
  });
});
