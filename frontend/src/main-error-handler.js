/**
 * Global Vue error handler.
 *
 * Exported as a separate module so main.js stays small and so tests
 * can exercise the configuration without mounting the whole app.
 */

/**
 * Configure the given Vue app with a global error handler.
 * @param {import('vue').App} app - The Vue application instance.
 * @param {(msg: string, meta?: object) => void} logError - Logger function.
 */
export function configureErrorHandler(app, logError) {
  app.config.errorHandler = (err, instance, info) => {
    const componentName = instance?.$?.type?.name || 'Unknown';
    logError(`Uncaught error in ${componentName}: ${err.message}`, {
      stack: err.stack,
      info,
    });
  };
}
