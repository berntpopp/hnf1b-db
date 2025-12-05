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
    vuetify({ autoImport: true }),

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
    // Hidden sourcemaps for error tracking (not linked from JS)
    sourcemap: 'hidden',

    rollupOptions: {
      output: {
        // Function-based chunk splitting for better granularity and caching
        manualChunks(id) {
          // Heavy visualization libraries - lazy loaded
          if (id.includes('chart.js')) return 'charts';
          if (id.includes('ngl')) return 'ngl-viewer';

          // D3 modules - used for visualizations
          if (id.includes('d3-') || id.includes('/d3/')) return 'd3-modules';

          // Vuetify data table components (heavy)
          if (id.includes('vuetify/lib/components/VDataTable')) {
            return 'vuetify-data';
          }
          if (id.includes('vuetify')) return 'vuetify-core';

          // Vue ecosystem
          if (id.includes('vue-router') || id.includes('pinia')) {
            return 'vue-core';
          }
          if (id.includes('/vue/') || id.includes('@vue/')) return 'vue-vendor';

          // Axios for API calls
          if (id.includes('axios')) return 'axios';

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
