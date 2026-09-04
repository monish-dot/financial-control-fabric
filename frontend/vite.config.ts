import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/events': 'http://127.0.0.1:8000',
      '/controls': 'http://127.0.0.1:8000',
      '/residuals': 'http://127.0.0.1:8000',
      '/reconciliation': 'http://127.0.0.1:8000',
      '/agent': 'http://127.0.0.1:8000',
      '/proofs': 'http://127.0.0.1:8000',
    },
  },
});
