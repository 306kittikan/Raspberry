/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans Thai"', '"Noto Sans Thai"', 'sans-serif'],
      },
      colors: {
        // อัตลักษณ์มหาวิทยาลัยแม่โจ้ - โทนเขียว
        brand: {
          50: '#F1FAF4',
          100: '#DCF2E4',
          200: '#B6E3C6',
          300: '#82CD9F',
          400: '#47B074',
          500: '#1E9455',
          600: '#0F7A43',
          700: '#0B6136',  // สีหลัก
          800: '#094C2B',
          900: '#063520',
        },
        ink: {
          DEFAULT: '#101C16',
          soft: '#3A4A41',
          mute: '#5C6B63',
        },
        ai: {
          50: '#F2EEFC',
          100: '#E5DCFA',
          600: '#5B32C4',
          700: '#4A2AA0',
          900: '#2E1A64',
        },
        alert: {
          50: '#FEF4E6',
          100: '#FCE7C4',
          700: '#8A4B07',
          900: '#5C3104',
        },
        danger: {
          50: '#FDECEC',
          100: '#FAD5D5',
          600: '#C42222',
          700: '#9B1B1B',
        },
      },
      fontSize: {
        // สเกลสำหรับอ่านจากระยะยืน 50-80 ซม.
        body: ['26px', { lineHeight: '1.5' }],
        'body-lg': ['30px', { lineHeight: '1.5' }],
        label: ['24px', { lineHeight: '1.4' }],
        h3: ['40px', { lineHeight: '1.25', letterSpacing: '-0.01em' }],
        h2: ['52px', { lineHeight: '1.2', letterSpacing: '-0.015em' }],
        h1: ['68px', { lineHeight: '1.15', letterSpacing: '-0.02em' }],
        mega: ['120px', { lineHeight: '1', letterSpacing: '-0.03em' }],
        clock: ['180px', { lineHeight: '1', letterSpacing: '-0.035em' }],
      },
      boxShadow: {
        // เงาสองชั้น ชั้นบางไว้แทนเส้นขอบ ชั้นฟุ้งไว้ยกพื้นผิวให้ลอย
        // ใช้แทนกรอบ 2px ทั้งหมด เพราะกรอบหนาทำให้ทุกอย่างดูเป็นกล่องแบน
        // ระวังบน Raspberry Pi — ใส่เฉพาะพื้นผิวที่อยู่นิ่ง ไม่ใส่ในรายการที่ซ้ำหลายสิบแถว
        card: '0 1px 2px rgba(6, 53, 32, 0.05), 0 8px 24px -6px rgba(6, 53, 32, 0.10)',
        'card-lg': '0 2px 4px rgba(6, 53, 32, 0.06), 0 20px 48px -12px rgba(6, 53, 32, 0.16)',
        hero: '0 4px 12px rgba(6, 53, 32, 0.18), 0 24px 56px -16px rgba(6, 53, 32, 0.40)',
        // ปุ่มหลักยกขึ้นเล็กน้อย ให้รู้ว่ากดได้โดยไม่ต้องมีกรอบ
        raise: '0 2px 4px rgba(6, 53, 32, 0.12), 0 10px 22px -8px rgba(11, 97, 54, 0.45)',
        inset: 'inset 0 1px 2px rgba(6, 53, 32, 0.08)',
      },
      borderRadius: {
        xl2: '20px',
        xl3: '28px',
        xl4: '34px',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'rise-in': {
          '0%': { opacity: '0', transform: 'translateY(24px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'scan-line': {
          '0%': { transform: 'translateY(0)' },
          '100%': { transform: 'translateY(420px)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(1)', opacity: '0.55' },
          '100%': { transform: 'scale(1.35)', opacity: '0' },
        },
        'wave': {
          '0%, 100%': { transform: 'scaleY(0.22)' },
          '50%': { transform: 'scaleY(1)' },
        },
        'dot': {
          '0%, 80%, 100%': { opacity: '0.25' },
          '40%': { opacity: '1' },
        },
        'spin-slow': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 220ms ease-out both',
        'rise-in': 'rise-in 260ms ease-out both',
        'scan-line': 'scan-line 2.2s ease-in-out infinite alternate',
        'pulse-ring': 'pulse-ring 1.6s ease-out infinite',
        'dot': 'dot 1.2s ease-in-out infinite',
        'spin-slow': 'spin-slow 1.1s linear infinite',
      },
    },
  },
  plugins: [],
}
