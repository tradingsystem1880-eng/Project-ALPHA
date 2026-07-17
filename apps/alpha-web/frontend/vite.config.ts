import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The SPA is built into the Python package's static/app dir and served by FastAPI from /static/app/.
// A dedicated subdir keeps the built assets isolated from the (transitional) legacy Jinja statics.
export default defineConfig({
  plugins: [react()],
  base: '/static/app/',
  build: {
    outDir: '../src/alpha_web/static/app',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
})
