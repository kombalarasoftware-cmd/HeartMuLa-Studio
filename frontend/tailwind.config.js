/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
            },
            colors: {
                glass: {
                    surface: "rgba(255, 255, 255, 0.4)",
                    border: "rgba(255, 255, 255, 0.2)",
                    text: "rgba(0, 0, 0, 0.8)",
                }
            },
            backdropBlur: {
                xs: '2px',
            },
            keyframes: {
                'float-note': {
                    '0%': { transform: 'translateY(0) rotate(0deg)', opacity: '0' },
                    '10%': { opacity: '1' },
                    '90%': { opacity: '1' },
                    '100%': { transform: 'translateY(-100vh) rotate(360deg)', opacity: '0' },
                },
                'pulse-circle': {
                    '0%, 100%': { transform: 'scale(1)', opacity: '0.4' },
                    '50%': { transform: 'scale(1.4)', opacity: '0.8' },
                },
                equalizer: {
                    '0%, 100%': { height: '4px' },
                    '50%': { height: 'var(--max-h, 30px)' },
                },
                shake: {
                    '0%, 100%': { transform: 'translateX(0)' },
                    '20%': { transform: 'translateX(-6px)' },
                    '40%': { transform: 'translateX(6px)' },
                    '60%': { transform: 'translateX(-4px)' },
                    '80%': { transform: 'translateX(4px)' },
                },
            },
            animation: {
                'float-note': 'float-note linear infinite',
                'pulse-circle': 'pulse-circle ease-in-out infinite',
                equalizer: 'equalizer ease-in-out infinite',
                shake: 'shake 0.4s ease-in-out',
            },
        },
    },
    plugins: [],
}
