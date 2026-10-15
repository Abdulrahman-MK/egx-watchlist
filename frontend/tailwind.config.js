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
        terminal: {
          bg: '#0a0d14',
          card: '#111622',
          cardHover: '#161c2b',
          border: '#1f293d',
          borderLight: '#2c3954',
          muted: '#8b9bb4',
          accent: '#38bdf8',
          up: '#10b981',
          upGlow: 'rgba(16, 185, 129, 0.25)',
          down: '#f43f5e',
          downGlow: 'rgba(244, 63, 94, 0.25)',
        }
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'Menlo', 'Monaco', 'Consolas', '"Liberation Mono"', '"Courier New"', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      keyframes: {
        flashGreen: {
          '0%': { backgroundColor: 'rgba(16, 185, 129, 0.45)', color: '#ffffff' },
          '100%': { backgroundColor: 'transparent' },
        },
        flashRed: {
          '0%': { backgroundColor: 'rgba(244, 63, 94, 0.45)', color: '#ffffff' },
          '100%': { backgroundColor: 'transparent' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.4 },
        }
      },
      animation: {
        flashGreen: 'flashGreen 1.2s cubic-bezier(0.4, 0, 0.2, 1)',
        flashRed: 'flashRed 1.2s cubic-bezier(0.4, 0, 0.2, 1)',
        pulseGlow: 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
