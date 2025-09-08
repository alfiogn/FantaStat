/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html", // Include your HTML files
  ],
  theme: {
    extend: {
      // Add custom colors, fonts, etc. here if needed
    },
  },
  plugins: [
    require('@tailwindcss/typography'), // For prose classes - great for markdown
  ],
  // Production optimizations
  purge: {
    enabled: process.env.NODE_ENV === 'production',
    content: ["./src/**/*.{js,jsx,ts,tsx}"],
  },
}