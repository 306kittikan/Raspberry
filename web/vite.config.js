import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ตอนพัฒนา หน้าเว็บอยู่พอร์ต 5173 และ API อยู่พอร์ต 8000
// proxy ทำให้หน้าเว็บเรียก /api และ /ws ได้เหมือนอยู่ origin เดียวกัน
// ซึ่งตรงกับตอนติดตั้งใช้งานจริงที่เซิร์ฟเวอร์เสิร์ฟทั้งหน้าเว็บและ API เอง
const API = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API, changeOrigin: true },
      '/ws': { target: API, ws: true, changeOrigin: true },
    },
  },
  build: { target: 'es2020' },
})
