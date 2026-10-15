/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0B1120',
        surface: {
          DEFAULT: '#162032',
          elevated: '#1E293B',
          hover: '#243247',
        },
        border: '#334155',
        primary: {
          DEFAULT: '#06B6D4',
          hover: '#0891B2',
          light: '#22D3EE',
          dark: '#0E7490',
        },
        teal: {
          DEFAULT: '#14B8A6',
          light: '#2DD4BF',
        },
        severity: {
          critical: '#EF4444',
          high: '#F59E0B',
          medium: '#38BDF8',
          low: '#10B981',
          backup: '#8B5CF6',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 20px -5px rgba(6, 182, 212, 0.3)',
        'glow-crimson': '0 0 20px -5px rgba(239, 68, 68, 0.3)',
      }
    },
  },
  plugins: [],
}
