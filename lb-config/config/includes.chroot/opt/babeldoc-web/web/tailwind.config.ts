import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f4ff",
          500: "#4f6ef7",
          600: "#3a57e8",
          700: "#2d46c9",
        },
      },
    },
  },
  plugins: [],
};

export default config;
