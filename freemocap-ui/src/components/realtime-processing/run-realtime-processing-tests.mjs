// From freemocap-ui: node src/components/realtime-processing/run-realtime-processing-tests.mjs
// Generated output belongs in core's ignored .test-artifacts directory.
import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import path from 'node:path';

// Every test file this runner bundles and runs. Append new ones here, and add each basename to
// `specialized` in tools/test-sdk-integration.mjs so that `npm test` runs it once, through this runner.
const TESTS = [
    'src/components/ui-components/Checkbox.test.tsx',
    'src/components/ui-components/ValueSelector.test.tsx',
    'src/components/processing-graph/stage-layout.test.ts',
    'src/components/mocap-setup/processing-outline.test.tsx',
];
const OUTPUT = '../.test-artifacts/realtime-processing-tests';

// One bundle per test file, named after it: basenames are unique under src.
// Components that read the store bring its modules with them: their layout presets are YAML, and their worker
// scripts are named by import.meta.url, which a CommonJS bundle leaves empty. No test here starts a worker.
await build({
    entryPoints: TESTS, outdir: OUTPUT, entryNames: '[name]', outExtension: {'.js': '.cjs'},
    bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic',
    alias: {'@': './src'}, loader: {'.css': 'empty', '.svg': 'dataurl', '.yaml': 'text'},
    logOverride: {'empty-import-meta': 'silent'},
});
const bundles = TESTS.map(test => `${OUTPUT}/${path.basename(test).replace(/\.tsx?$/, '.cjs')}`);
// The tests inherit this process's environment, and a failing test fails the runner.
const result = spawnSync(process.execPath, ['--test', ...bundles], {stdio: 'inherit', env: process.env});
process.exitCode = result.status ?? 1;
