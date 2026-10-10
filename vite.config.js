import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vuetify from "vite-plugin-vuetify";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  root: "frontend",
  publicDir: false,
  plugins: [vue(), vuetify({ autoImport: true }), tailwindcss()],
  build: { outDir: "../public", emptyOutDir: false },
  server: { proxy: { "/api": "http://127.0.0.1:3000" } },
});
