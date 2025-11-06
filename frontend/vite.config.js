// vite.config.js
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import vuetify from 'vite-plugin-vuetify';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    vue(),
    vuetify({ autoImport: true }),

    // Bundle size visualization (all environments)
    // Creates dist/bundle-analysis.html after build
    visualizer({
      filename: 'dist/bundle-analysis.html',
      open: false,
      gzipSize: true,
      brotliSize: true,
      template: 'treemap',
    }),
  ],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    // Prevent duplicate Vue instances (can cause hydration issues)
    // Proven optimization from agde-frontend
    dedupe: ['vue', 'vuetify'],
  },

  optimizeDeps: {
    // Pre-bundle heavy dependencies for faster cold starts
    include: ['vue', 'vue-router', 'vuetify', 'd3', 'axios'],
  },

  server: {
    port: 5173,
    strictPort: false,

    // Vite 6 feature: Pre-transform frequently accessed files
    // Significantly improves first-page load time
    // Proven optimization from agde-frontend
    warmup: {
      clientFiles: [
        './src/views/Home.vue',
        './src/views/PageVariant.vue',
        './src/components/gene/HNF1BGeneVisualization.vue',
        './src/components/gene/HNF1BProteinVisualization.vue',
      ],
    },

    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },

    watch: {
      // Only use polling on Linux/WSL (not needed on macOS/Windows)
      usePolling: process.platform === 'linux',
    },
  },

  build: {
    // Enable sourcemaps for production debugging
    sourcemap: true,

    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching
        // Users only re-download changed chunks
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router'],
          vuetify: ['vuetify'],
          d3: ['d3'],
          axios: ['axios'],
        },
      },
    },

    // Modern build target (smaller bundles)
    target: 'esnext',

    // Terser minification (better than esbuild for production)
    minify: 'terser',
    terserOptions: {
      compress: {
        // Remove console.log and debugger from production
        drop_console: true,
        drop_debugger: true,
      },
    },
  },
});
