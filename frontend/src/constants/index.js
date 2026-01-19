/**
 * Centralized Constants Module
 *
 * For tree-shaking optimization, prefer direct imports:
 *   import { STRUCTURE_START } from '@/constants/structure';
 *
 * Barrel import available for convenience:
 *   import { STRUCTURE_START, DISTANCE_CLOSE_THRESHOLD } from '@/constants';
 */

export * from './thresholds.js';
export * from './structure.js';
export * from './ui.js';
