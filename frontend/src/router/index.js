import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import(/* webpackChunkName: "home" */ '../views/Home.vue'),
  },
  {
    path: '/phenopackets',
    name: 'Phenopackets',
    component: () => import(/* webpackChunkName: "phenopackets" */ '../views/Phenopackets.vue'),
  },
  {
    path: '/phenopackets/:phenopacket_id',
    name: 'PagePhenopacket',
    component: () =>
      import(/* webpackChunkName: "page-phenopacket" */ '../views/PagePhenopacket.vue'),
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
  },
  {
    path: '/publications/:publication_id',
    name: 'PagePublication',
    component: () =>
      import(/* webpackChunkName: "page-publication" */ '../views/PagePublication.vue'),
  },
  {
    path: '/variants',
    name: 'Variants',
    component: () => import(/* webpackChunkName: "variants" */ '../views/Variants.vue'),
  },
  {
    path: '/variants/:variant_id',
    name: 'PageVariant',
    component: () => import(/* webpackChunkName: "page-variant" */ '../views/PageVariant.vue'),
  },
  {
    path: '/aggregations',
    name: 'Aggregations',
    component: () =>
      import(/* webpackChunkName: "aggregations" */ '../views/AggregationsDashboard.vue'),
  },
  {
    path: '/search',
    name: 'SearchResults',
    component: () => import(/* webpackChunkName: "search-results" */ '../views/SearchResults.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import(/* webpackChunkName: "login" */ '../views/Login.vue'),
  },
  {
    path: '/user',
    name: 'User',
    component: () => import(/* webpackChunkName: "user" */ '../views/User.vue'),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
