/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    // Scan main app source too — @main alias imports use Tailwind classes
    '../../frontend/src/**/*.{js,ts,jsx,tsx}',
    // Docker build copies main app to ./main-app-src
    './main-app-src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: { extend: {} },
  plugins: [],
}
