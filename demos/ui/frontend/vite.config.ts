import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// Shared proxy configuration
const proxyConfig = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    secure: false,
    rewrite: (path) => path.replace(/^\/api/, '/api'),
    configure: (proxy, _options) => {
      proxy.on('error', (err: NodeJS.ErrnoException, _req, _res) => {
        console.log('proxy error', err);
        if (err.code && err.code === 'ECONNREFUSED') {
          console.log('Backend server might be down, please check the connection');
        }
      });
      proxy.on('proxyReq', (proxyReq, req, _res) => {
        console.log('Sending Request to the Target:', req.method, req.url);
      });
      proxy.on('proxyRes', (proxyRes, req, _res) => {
        console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
      });
    },
  },
  '/ws': {
    target: 'ws://127.0.0.1:8000',
    ws: true,
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/ws/, '/ws'),
    configure: (proxy, _options) => {
      proxy.on('error', (err: NodeJS.ErrnoException, _req, _res) => {
        console.log('WebSocket proxy error', err);
        if (err.code && err.code === 'ECONNREFUSED') {
          console.log('WebSocket server might be down, please check the connection');
        }
      });
      proxy.on('open', () => {
        console.log('WebSocket connection established');
      });
      proxy.on('close', () => {
        console.log('WebSocket connection closed');
      });
    },
  }
};

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
  ].filter(Boolean),
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '@components': resolve(__dirname, './src/components'),
      '@pages': resolve(__dirname, './src/pages'),
      '@hooks': resolve(__dirname, './src/hooks'),
      '@utils': resolve(__dirname, './src/utils'),
      '@types': resolve(__dirname, './src/types'),
      '@services': resolve(__dirname, './src/services'),
      '@store': resolve(__dirname, './src/store'),
      '@styles': resolve(__dirname, './src/styles'),
      '@assets': resolve(__dirname, './src/assets'),
      '@layouts': resolve(__dirname, './src/layouts')
    }
  },
  server: {
    port: 5173,
    proxy: proxyConfig
  },
  preview: {
    port: 4173,
    host: true, // needed for network access
    proxy: proxyConfig
  },
  build: {
    target: 'esnext',
    outDir: 'dist',
    sourcemap: mode === 'development',
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-markdown': [
            'react-markdown',
            'react-markdown-editor-lite',
            'remark-gfm',
            'remark-math',
            'rehype-katex'
          ],
          'vendor-ui': ['@headlessui/react', '@heroicons/react', 'react-icons'],
          'vendor-utils': ['date-fns', 'clsx', 'tailwind-merge'],
          'vendor-katex': ['katex', 'github-markdown-css'],
          'vendor-syntax': ['highlight.js', 'react-syntax-highlighter']
        },
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.');
          const ext = info[info.length - 1];
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(ext)) {
            return `assets/images/[name]-[hash][extname]`;
          }
          return `assets/[name]-[hash][extname]`;
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom'],
    exclude: ['@tailwindcss/forms', '@tailwindcss/typography', '@tailwindcss/aspect-ratio'],
  },
}))
