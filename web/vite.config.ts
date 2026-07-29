import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [svelte()],
  resolve: {
    conditions: ["browser"]
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000"
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.ts"],
    setupFiles: ["./src/test/setup.ts"]
  }
});
