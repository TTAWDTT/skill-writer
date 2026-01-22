/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary accent
        'anthropic': {
          'orange': '#E36A3A',
          'orange-light': '#F0A384',
          'orange-dark': '#C7562C',
        },
        // Dark surfaces
        'warm': {
          '50': '#0E1116',
          '100': '#141A21',
          '200': '#1B2230',
          '300': '#243044',
          '400': '#2F3C55',
        },
        // Text tones
        'dark': {
          '50': '#9FB1C3',
          '100': '#B7C3D6',
          '200': '#D5DDE9',
          '300': '#EEF2F7',
          '400': '#F8FAFC',
        },
        // Signal accents
        'signal': {
          '50': '#102A2E',
          '100': '#16363C',
          '200': '#1D4A52',
          '300': '#23606B',
          '400': '#2B7986',
          '500': '#3194A4',
          '600': '#46AEBB',
          '700': '#77CBD3',
        },
      },
      fontFamily: {
        'sans': ['"IBM Plex Sans"', '"Noto Sans SC"', 'sans-serif'],
        'display': ['"Space Grotesk"', '"Noto Sans SC"', 'sans-serif'],
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
      },
    },
  },
  plugins: [],
}
