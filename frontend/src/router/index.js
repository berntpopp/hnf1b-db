import { createRouter, createWebHistory } from 'vue-router';
import { updatePageTitle } from '@/composables/usePageTitle';
import { useAuthStore } from '@/stores/authStore';

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
    path: '/phenopackets/create',
    name: 'CreatePhenopacket',
    component: () =>
      import(
        /* webpackChunkName: "phenopacket-create-edit" */ '../views/PhenopacketCreateEdit.vue'
      ),
    meta: { title: 'Create Phenopacket', requiresAuth: true },
  },
  {
    path: '/phenopackets/:phenopacket_id/edit',
    name: 'EditPhenopacket',
    component: () =>
      import(
        /* webpackChunkName: "phenopacket-create-edit" */ '../views/PhenopacketCreateEdit.vue'
      ),
    meta: { title: 'Edit Phenopacket', requiresAuth: true },
  },
  {
    path: '/phenopackets/:phenopacket_id',
    name: 'PagePhenopacket',
    component: () =>
      import(/* webpackChunkName: "page-phenopacket" */ '../views/PagePhenopacket.vue'),
    meta: { title: 'Phenopacket Details' },
  },
  // Redirects for backward compatibility (permanent)
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
    meta: { title: 'User Profile', requiresAuth: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Global navigation guard: Check authentication before each route
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();

  // Check if route requires authentication
  if (to.meta.requiresAuth) {
    // Check if user has a valid access token
    if (!authStore.accessToken) {
      // No token, redirect to login with return URL
      window.logService.info('Route requires authentication, redirecting to login', {
        from: from.path,
        to: to.path,
      });
      next({
        name: 'Login',
        query: { redirect: to.fullPath },
      });
      return;
    }
    // Has token, allow navigation (component will fetch user data if needed)
  } else if (to.name === 'Login' && authStore.accessToken) {
    // User already has token, redirect to home
    window.logService.info('User already authenticated, redirecting to home');
    next({ name: 'Home' });
    return;
  }

  // All good, proceed with navigation
  next();
});

// Global navigation guard to update page title dynamically
// Uses afterEach to avoid blocking navigation and ensure the route has changed
router.afterEach((to) => {
  // Get the title from route meta, or use empty string for default
  const pageTitle = to.meta?.title || '';
  updatePageTitle(pageTitle);
});

export default router;
