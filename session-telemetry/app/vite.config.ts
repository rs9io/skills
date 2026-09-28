import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Built by install.sh and served by server.mjs at http://localhost:4200.
export default defineConfig({
	plugins: [react(), tailwindcss()],
	resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
	server: { proxy: { "/api": "http://localhost:4200" } },
})
