/**
 * Navigation Items Configuration
 * Single source of truth for app navigation (DRY principle)
 * Used by AppBar (desktop) and MobileDrawer (mobile)
 */

export const navigationItems = [
  {
    icon: 'mdi-account-multiple',
    label: 'Phenopackets',
    route: '/phenopackets',
    requiresAuth: false,
  },
  {
    icon: 'mdi-book-open-variant',
    label: 'Publications',
    route: '/publications',
    requiresAuth: false,
  },
  {
    icon: 'mdi-dna',
    label: 'Variants',
    route: '/variants',
    requiresAuth: false,
  },
  {
    icon: 'mdi-chart-bar',
    label: 'Aggregations',
    route: '/aggregations',
    requiresAuth: false,
  },
];
