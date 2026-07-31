/**
 * Render an API error into a message a curator can act on.
 *
 * The phenopacket write endpoints reject invalid documents with a structured
 * body (backend/app/phenopackets/routers/crud.py):
 *
 *   400 { "detail": { "validation_errors": ["subject.id: '' is too short", ...] } }
 *
 * Every call site in this app used to build its message with
 * `'...: ' + err.response?.data?.detail`, which stringifies that object to
 * "[object Object]" — the curator is told the save failed but not which of the
 * fields the console writes was rejected, and the actual reason is discarded.
 *
 * Shapes handled, in order of specificity:
 *   - `detail` is a string                     → used verbatim
 *   - `detail.validation_errors` is an array   → the individual messages
 *   - `detail.message` is a string             → used (Wave 7 D.1 {code,message})
 *   - `detail` is a FastAPI 422 array          → "loc.path: msg" per entry
 *   - `detail` is any other object             → JSON, so nothing is silently lost
 *   - otherwise                                → `err.message`, then `fallback`
 */

/** Cap on listed validation errors; the rest are counted, never dropped silently. */
const MAX_LISTED = 10;

function joinMessages(messages) {
  const cleaned = messages.map((m) => String(m).trim()).filter(Boolean);
  if (cleaned.length === 0) return '';
  if (cleaned.length <= MAX_LISTED) return cleaned.join('; ');
  const shown = cleaned.slice(0, MAX_LISTED).join('; ');
  return `${shown}; (+${cleaned.length - MAX_LISTED} more)`;
}

/**
 * @param {unknown} detail the `response.data.detail` value, any shape
 * @returns {string} a human-readable rendering, or '' if there is nothing to say
 */
export function formatErrorDetail(detail) {
  if (detail == null) return '';
  if (typeof detail === 'string') return detail.trim();

  if (Array.isArray(detail)) {
    // FastAPI's own 422 shape: [{ loc: [...], msg: '...' }, ...]
    return joinMessages(
      detail.map((entry) => {
        if (typeof entry === 'string') return entry;
        const loc = Array.isArray(entry?.loc) ? entry.loc.join('.') : '';
        const msg = entry?.msg ?? entry?.message ?? JSON.stringify(entry);
        return loc ? `${loc}: ${msg}` : String(msg);
      })
    );
  }

  if (typeof detail === 'object') {
    if (Array.isArray(detail.validation_errors)) {
      const joined = joinMessages(detail.validation_errors);
      if (joined) return joined;
    }
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message.trim();
    }
    // Never fall through to "[object Object]": show the payload instead.
    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }

  return String(detail);
}

/**
 * @param {any} err an axios-style error
 * @param {string} fallback used when the error carries no usable message
 * @returns {string}
 */
export function formatApiError(err, fallback = 'Request failed') {
  const fromDetail = formatErrorDetail(err?.response?.data?.detail);
  if (fromDetail) return fromDetail;
  const message = typeof err?.message === 'string' ? err.message.trim() : '';
  return message || fallback;
}
