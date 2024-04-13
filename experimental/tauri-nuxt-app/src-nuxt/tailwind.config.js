import colors from "tailwindcss/colors";

/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./components/**/*.{js,vue,ts}",
        "./layouts/**/*.vue",
        "./pages/**/*.vue",
        "./plugins/**/*.{js,ts}",
        "./app.vue",
        "./error.vue",
    ],
    theme: {
        extend: {
            colors: {
                primary: '#003535',
                secondary: '#002020',
                tertiary: '#94c4c7',
                accent: '#d64550',
                gray: colors.neutral,
                grey: colors.neutral,
            },
        },
    },
    plugins: [],
}

