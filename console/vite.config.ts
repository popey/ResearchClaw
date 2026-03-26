import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.indexOf("node_modules") === -1) return;
          if (
            id.indexOf("react-markdown") !== -1 ||
            id.indexOf("remark-") !== -1 ||
            id.indexOf("rehype-") !== -1 ||
            id.indexOf("katex") !== -1
          ) {
            return "markdown";
          }
          if (id.indexOf("lucide-react") !== -1) {
            return "icons";
          }
          return;
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
      },
    },
  },
});
