/** @type {import('tailwindcss').Config} */
import colors from 'tailwindcss/colors.js'

export default {
  mode: 'jit',
  content: [
    // Example content paths...
    './public/**/*.html',
    './src/**/*.{js,jsx,ts,tsx,vue}'
  ],
  theme: {
    extend: {
      colors: {
        primary: '#003535',
        secondary: '#002020',
        tertiary: '#94c4c7',
        highlight: '#d64550',
        gray: colors.neutral,
        black: colors.black,
        white: colors.white,
        blue: colors.blue,
        red: colors.red,
        green: colors.green,
        yellow: colors.yellow,
        pink: colors.pink,
        purple: colors.purple
      }
    }
  },
  plugins: []
}
