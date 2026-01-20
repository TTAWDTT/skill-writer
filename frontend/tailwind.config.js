/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Anthropic 品牌色
        'anthropic': {
          'orange': '#D97757',
          'orange-light': '#E8A88E',
          'orange-dark': '#C25E3D',
        },
        // 暖色调背景
        'warm': {
          '50': '#FDFCFB',
          '100': '#FAF9F6',
          '200': '#F5F3EF',
          '300': '#E8E4DD',
          '400': '#D1CBC0',
        },
        // 深色模式
        'dark': {
          '50': '#2D2D2B',
          '100': '#252523',
          '200': '#1F1F1D',
          '300': '#191918',
          '400': '#131312',
        },
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        'serif': ['Palatino', 'Georgia', 'serif'],
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
      },
    },
  },
  plugins: [],
}
