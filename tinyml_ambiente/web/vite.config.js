import { defineConfig } from 'vite';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

// Prebundle the chart dependency to keep Rollup's CommonJS analysis fast on Windows.
export default defineConfig(async ({ command }) => {
  if (command !== 'build') return {};
  const root = fileURLToPath(new URL('.', import.meta.url));
  const outfile = fileURLToPath(new URL('./node_modules/.cache/ambiente-charts.js', import.meta.url));
  await build({ stdin: { contents: "export { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts';", resolveDir: root }, bundle: true, format: 'esm', platform: 'browser', external: ['react', 'react-dom'], outfile });
  return { resolve: { alias: { recharts: outfile } }, build: { rollupOptions: { treeshake: false } } };
});
