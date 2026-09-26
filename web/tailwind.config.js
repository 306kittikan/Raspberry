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
        h3: ['40px', { lineHeight: '1.25' }],
        h2: ['52px', { lineHeight: '1.2' }],
        h1: ['68px', { lineHeight: '1.15' }],
        mega: ['120px', { lineHeight: '1' }],
        clock: ['180px', { lineHeight: '1' }],
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
