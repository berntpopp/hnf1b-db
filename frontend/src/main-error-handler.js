/**
 * Global Vue error handler.
 *
 * Exported as a separate module so main.js stays small and so tests
 * can exercise the configuration without mounting the whole app.
 */

/**
 * Configure the given Vue app with a global error handler.
 *
 * Vue's errorHandler signature allows `err` to be any thrown value, not
 * just an `Error` instance (code paths can `throw "string"` or
 * `throw { code: 42 }`). We defensively derive a message without
 * assuming `.message`/`.stack` exist, so the handler itself never
 * throws and swallows the original error.
 *
 * @param {import('vue').App} app - The Vue application instance.
 * @param {(msg: string, meta?: object) => void} logError - Logger function.
 */
export function configureErrorHandler(app, logError) {
  app.config.errorHandler = (err, instance, info) => {
    const componentName = instance?.$?.type?.name || 'Unknown';
    const message = err instanceof Error ? err.message : String(err);
    const stack = err instanceof Error ? err.stack : undefined;
    logError(`Uncaught error in ${componentName}: ${message}`, {
      stack,
      info,
    });
  };
}
