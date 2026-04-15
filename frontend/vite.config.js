// vite.config.js
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import vuetify from 'vite-plugin-vuetify';
import { visualizer } from 'rollup-plugin-visualizer';
import compression from 'vite-plugin-compression';

export default defineConfig({
  plugins: [
    vue(),
    // Restore Material Design 2 typography (Roboto + larger heading scale +
    // uppercase buttons) so Vuetify 4's MD3 defaults don't regress the
    // current production look. Overrides live in src/styles/settings.scss.
    vuetify({
      autoImport: true,
      styles: { configFile: 'src/styles/settings.scss' },
    }),

    // Brotli compression (best compression, ~20% smaller than gzip)
    compression({
      algorithm: 'brotliCompress',
      ext: '.br',
      threshold: 1024,
      exclude: [/\.(png|jpg|jpeg|gif|webp|avif|ico)$/i],
    }),

    // Gzip compression (fallback for older browsers)
    compression({
      algorithm: 'gzip',
      ext: '.gz',
      threshold: 1024,
      exclude: [/\.(png|jpg|jpeg|gif|webp|avif|ico)$/i],
    }),

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

    // Proxy target: only the origin portion of VITE_API_URL.
    //
    // VITE_API_URL is doing double-duty in this repo: axios (transport.js)
    // uses it as its baseURL (typically ending in /api/v2), while the Vite
    // proxy here needs the bare origin so that /api and /health rewrite
    // to the correct backend paths. Without this strip, running
    //   VITE_API_URL=http://localhost:8000/api/v2 npx vite
    // would proxy /health to /api/v2/health and get a 404.
    proxy: (() => {
      const raw = process.env.VITE_API_URL || 'http://localhost:8000';
      let target;
      try {
        target = new URL(raw).origin;
      } catch {
        target = 'http://localhost:8000';
      }
      return {
        '/api': { target, changeOrigin: true },
        // Health check endpoint for backend monitoring
        '/health': { target, changeOrigin: true },
      };
    })(),

    watch: {
      // Only use polling on Linux/WSL (not needed on macOS/Windows)
      usePolling: process.platform === 'linux',
    },
  },

  build: {
    // Hidden sourcemaps for error tracking (not linked from JS)
    sourcemap: 'hidden',

    rollupOptions: {
      output: {
        // Function-based chunk splitting for better granularity and caching
        // Smaller chunks = better cache invalidation + parallel loading
        manualChunks(id) {
          // Heavy visualization libraries - lazy loaded on demand
          if (id.includes('chart.js')) return 'charts';
          if (id.includes('ngl')) return 'ngl-viewer';

          // D3 modules - used for visualizations
          if (id.includes('d3-') || id.includes('/d3/')) return 'd3-modules';

          // Vuetify data table components (heavy, often lazy loaded)
          if (id.includes('vuetify/lib/components/VDataTable')) {
            return 'vuetify-data';
          }
          if (id.includes('vuetify')) return 'vuetify-core';

          // Vue ecosystem - core framework
          if (id.includes('vue-router') || id.includes('pinia')) {
            return 'vue-core';
          }
          if (id.includes('/vue/') || id.includes('@vue/')) return 'vue-vendor';

          // Axios for API calls - frequently used
          if (id.includes('axios')) return 'axios';

          // Date utilities - split for better caching
          if (id.includes('date-fns')) return 'date-utils';

          // Form validation - only needed on edit pages
          if (id.includes('yup')) return 'validation';

          // File utilities - only needed for downloads
          if (id.includes('file-saver')) return 'file-utils';

          // Other node_modules
          if (id.includes('node_modules')) return 'vendor';
        },
      },
    },

    // Alert on large chunks (300KB threshold)
    chunkSizeWarningLimit: 300,

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
