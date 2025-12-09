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
    tooltip: 'Browse patient clinical & genetic profiles',
    requiresAuth: false,
  },
  {
    icon: 'mdi-book-open-variant',
    label: 'Publications',
    route: '/publications',
    tooltip: 'Explore research publications & references',
    requiresAuth: false,
  },
  {
    icon: 'mdi-dna',
    label: 'Variants',
    route: '/variants',
    tooltip: 'Search HNF1B genetic variants',
    requiresAuth: false,
  },
  {
    icon: 'mdi-chart-bar',
    label: 'Aggregations',
    route: '/aggregations',
    tooltip: 'View statistics & data visualizations',
    requiresAuth: false,
  },
];
