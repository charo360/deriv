/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        deriv: {
          red: '#ff444f',
          green: '#00a79e',
          dark: '#0e0e0e',
          gray: '#1a1a1a',
          light: '#2a2a2a',
        }
      }
    },
  },
  plugins: [],
}
