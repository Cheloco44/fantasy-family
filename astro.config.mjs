import { defineConfig } from 'astro/config';
// Public deployment is deliberately not configured. Set BASE_PATH for Pages later.
export default defineConfig({ output: 'static', base: process.env.BASE_PATH || '/', trailingSlash: 'always' });
