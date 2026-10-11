import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend (backend/main.py) allows exactly this origin, so the port is fixed:
// if 5173 is busy Vite stops instead of quietly moving to a port the backend would reject.
// `npm run dev` opens the desk in your browser; set NO_OPEN=1 to skip that (e.g. in tests).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    open: !process.env.NO_OPEN,
  },
})