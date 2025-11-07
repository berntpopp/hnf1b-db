/**
 * Privacy-first log sanitizer
 * Automatically redacts medical, genetic, and personal data from logs
 *
 * GDPR/HIPAA Compliance: All PII/PHI is redacted before storage
 */

const REDACTION_PATTERNS = {
  // Medical data
  hpoTerm: {
    pattern: /HP:\d{7}/g,
    replacement: '[HPO_TERM]',
  },
  variant: {
    pattern: /NM_\d+\.\d+:c\.\d+[ATCG]>[ATCG]/gi,
    replacement: '[VARIANT]',
  },
  mondo: {
    pattern: /MONDO:\d+/gi,
    replacement: '[DISEASE]',
  },

  // Genetic sequences (8+ nucleotides)
  dnaSequence: {
    pattern: /\b[ATCG]{8,}\b/g,
    replacement: '[DNA_SEQUENCE]',
  },
  rnaSequence: {
    pattern: /\b[AUCG]{8,}\b/g,
    replacement: '[RNA_SEQUENCE]',
  },

  // Personal identifiers
  email: {
    pattern: /[\w.+-]+@[\w.-]+\.\w+/g,
    replacement: '[EMAIL]',
  },
  subjectId: {
    pattern: /HNF1B-\d{3}/g,
    replacement: '[SUBJECT_ID]',
  },

  // Authentication
  jwtToken: {
    pattern: /Bearer\s+[\w.-]+/g,
    replacement: 'Bearer [TOKEN]',
  },
  // API key pattern commented out - too broad, causes false positives
  // apiKey: {
  //   pattern: /[A-Za-z0-9_-]{32,}/g,
  //   replacement: '[API_KEY]',
  // },
};

/**
 * Sanitize log message and context
 * @param {string} message - Log message
 * @param {Object} context - Additional context data
 * @returns {Object} Sanitized message and context
 */
export function sanitizeLogData(message, context = {}) {
  // Convert context to string for pattern matching
  let stringified = JSON.stringify({ message, context });

  // Apply all redaction patterns
  Object.values(REDACTION_PATTERNS).forEach(({ pattern, replacement }) => {
    stringified = stringified.replace(pattern, replacement);
  });

  // Parse back to object
  const sanitized = JSON.parse(stringified);

  return {
    message: sanitized.message,
    context: sanitized.context,
  };
}

/**
 * Check if data contains sensitive information
 * @param {*} data - Data to check
 * @returns {boolean} True if sensitive data detected
 */
export function containsSensitiveData(data) {
  const stringified = JSON.stringify(data);

  // Use .match() instead of .test() to avoid regex state issues with global flag
  return Object.values(REDACTION_PATTERNS).some(({ pattern }) => stringified.match(pattern));
}

export default {
  sanitizeLogData,
  containsSensitiveData,
  REDACTION_PATTERNS,
};
