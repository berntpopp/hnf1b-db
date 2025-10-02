import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import(/* webpackChunkName: "home" */ '../views/Home.vue'),
  },
  {
    path: '/individuals',
    name: 'Individuals',
    component: () => import(/* webpackChunkName: "individuals" */ '../views/Individuals.vue'),
  },
  {
    path: '/individuals/:individual_id',
    name: 'PageIndividual',
    component: () =>
      import(/* webpackChunkName: "page-individual" */ '../views/PageIndividual.vue'),
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
