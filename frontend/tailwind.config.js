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
          'orange': '#F07C4A',
          'orange-light': '#F6A37E',
          'orange-dark': '#D86637',
        },
        // Dark surfaces
        'warm': {
          '50': '#0B0C0E',
          '100': '#111214',
          '200': '#171A1F',
          '300': '#1F232A',
          '400': '#2A303A',
        },
        // Text tones
        'dark': {
          '50': '#8C94A1',
          '100': '#AAB1BC',
          '200': '#C9CFD8',
          '300': '#E7EBF1',
          '400': '#F7F8FA',
        },
        // Signal accents
        'signal': {
          '50': '#0F141B',
          '100': '#141C26',
          '200': '#1A2531',
          '300': '#223242',
          '400': '#2B4056',
          '500': '#36526D',
          '600': '#496E90',
          '700': '#83A9C4',
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
