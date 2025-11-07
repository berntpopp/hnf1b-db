import { createRouter, createWebHistory } from 'vue-router';
import { updatePageTitle } from '@/composables/usePageTitle';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import(/* webpackChunkName: "home" */ '../views/Home.vue'),
    meta: { title: 'Home' },
  },
  {
    path: '/phenopackets',
    name: 'Phenopackets',
    component: () => import(/* webpackChunkName: "phenopackets" */ '../views/Phenopackets.vue'),
    meta: { title: 'Phenopackets' },
  },
  {
    path: '/phenopackets/:phenopacket_id',
    name: 'PagePhenopacket',
    component: () =>
      import(/* webpackChunkName: "page-phenopacket" */ '../views/PagePhenopacket.vue'),
    meta: { title: 'Phenopacket Details' },
  },
  // Legacy redirects for backward compatibility
  {
    path: '/individuals',
    redirect: '/phenopackets',
  },
  {
    path: '/individuals/:individual_id',
    redirect: (to) => `/phenopackets/${to.params.individual_id}`,
  },
  {
    path: '/publications',
    name: 'Publications',
    component: () => import(/* webpackChunkName: "publications" */ '../views/Publications.vue'),
    meta: { title: 'Publications' },
  },
  {
    path: '/publications/:publication_id',
    name: 'PagePublication',
    component: () =>
      import(/* webpackChunkName: "page-publication" */ '../views/PagePublication.vue'),
    meta: { title: 'Publication Details' },
  },
  {
    path: '/variants',
    name: 'Variants',
    component: () => import(/* webpackChunkName: "variants" */ '../views/Variants.vue'),
    meta: { title: 'Variants' },
  },
  {
    path: '/variants/:variant_id',
    name: 'PageVariant',
    component: () => import(/* webpackChunkName: "page-variant" */ '../views/PageVariant.vue'),
    meta: { title: 'Variant Details' },
  },
  {
    path: '/aggregations',
    name: 'Aggregations',
    component: () =>
      import(/* webpackChunkName: "aggregations" */ '../views/AggregationsDashboard.vue'),
    meta: { title: 'Statistics & Aggregations' },
  },
  {
    path: '/search',
    name: 'SearchResults',
    component: () => import(/* webpackChunkName: "search-results" */ '../views/SearchResults.vue'),
    meta: { title: 'Search Results' },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import(/* webpackChunkName: "login" */ '../views/Login.vue'),
    meta: { title: 'Login' },
  },
  {
    path: '/user',
    name: 'User',
    component: () => import(/* webpackChunkName: "user" */ '../views/User.vue'),
    meta: { title: 'User Profile' },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Global navigation guard to update page title dynamically
// Uses afterEach to avoid blocking navigation and ensure the route has changed
router.afterEach((to) => {
  // Get the title from route meta, or use empty string for default
  const pageTitle = to.meta?.title || '';
  updatePageTitle(pageTitle);
});

export default router;
