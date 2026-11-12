import { defineConfig } from 'astro/config';
// Keep local builds at root; the Pages workflow sets BASE_PATH=/fantasy-family/.
export default defineConfig({ output: 'static', site: 'https://cheloco44.github.io', base: process.env.BASE_PATH || '/', trailingSlash: 'always' });
