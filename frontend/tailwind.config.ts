import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17211c',
        cream: '#f6f4ed',
        sage: { 50: '#f3f7f4', 100: '#e1ebe3', 500: '#527c5b', 600: '#3f6749', 700: '#31543b' },
        amber: { 100: '#f8ead0', 500: '#c7862f' },
      },
      boxShadow: { card: '0 14px 40px rgba(28, 45, 34, 0.08)' },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui'], serif: ['Lora', 'Georgia', 'serif'] },
    },
  },
  plugins: [],
} satisfies Config

