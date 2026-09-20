/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        google: {
          blue: "#1A73E8",
          red: "#D93025",
          yellow: "#F9AB00",
          green: "#188038",
          gray: {
            50: "#F8F9FA",
            100: "#F1F3F4",
            200: "#E8EAED",
            300: "#DADCE0",
            400: "#BDC1C6",
            500: "#80868B",
            700: "#5F6368",
            800: "#3C4043",
            900: "#202124",
          },
        },
        vfx: {
          dark: "#090d16",
          panel: "#0f172a",
          border: "#1e293b",
          card: "#131d33",
          accent: "#38bdf8",
          neon: "#00f0ff",
        },
      },
    },
  },
  plugins: [],
};
