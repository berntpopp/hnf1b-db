/**
 * Dev-auth feature flag helpers.
 *
 * The frontend must not expose the quick-login surface just because Vite is
 * running in dev mode. Requiring an explicit flag keeps the UI aligned with the
 * backend's explicit ENVIRONMENT/ENABLE_DEV_AUTH gate.
 */

function isTruthyFlag(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value ?? '').toLowerCase());
}

export function isDevQuickLoginEnabled() {
  return import.meta.env.DEV && isTruthyFlag(import.meta.env.VITE_ENABLE_DEV_AUTH);
}

export function getDevQuickLoginDisabledMessage() {
  return 'Dev quick-login is disabled. Set VITE_ENABLE_DEV_AUTH=true and restart the frontend.';
}

export function getDevQuickLoginBackendUnavailableMessage() {
  return 'Dev quick-login is disabled on the backend. Set ENVIRONMENT=development and ENABLE_DEV_AUTH=true, then seed fixture users.';
}
