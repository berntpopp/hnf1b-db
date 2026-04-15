// src/api/index.js — Re-export aggregator
// Preserves both named exports AND the legacy `export default` shape.

export { apiClient } from './transport';
export {
  getAccessToken,
  getCsrfToken,
  persistTokens,
  clearTokens,
  setAccessToken,
} from './session';

export * from './domain/phenopackets';
export * from './domain/aggregations';
export * from './domain/admin';
export * from './domain/publications';
export * from './domain/auth';
export * from './domain/hpo';
export * from './domain/clinical';
export * from './domain/variants';
export * from './domain/reference';
export * from './domain/variant_annotation';
export * from './domain/search';

// Legacy default export — used by `import API from '@/api'`
import { apiClient } from './transport';
import * as phenopackets from './domain/phenopackets';
import * as aggregations from './domain/aggregations';
import * as admin from './domain/admin';
import * as publications from './domain/publications';
import * as auth from './domain/auth';
import * as hpo from './domain/hpo';
import * as clinical from './domain/clinical';
import * as variants from './domain/variants';
import * as reference from './domain/reference';
import * as variantAnnotation from './domain/variant_annotation';
import * as search from './domain/search';

export default {
  ...phenopackets,
  ...aggregations,
  ...admin,
  ...publications,
  ...auth,
  ...hpo,
  ...clinical,
  ...variants,
  ...reference,
  ...variantAnnotation,
  ...search,
  client: apiClient,
};
