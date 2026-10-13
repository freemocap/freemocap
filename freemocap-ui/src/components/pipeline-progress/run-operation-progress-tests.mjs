// From freemocap-ui: node src/components/pipeline-progress/run-operation-progress-tests.mjs
// Generated output belongs in core's ignored .test-artifacts directory.
import {build} from 'esbuild';
import {execFileSync} from 'node:child_process';
await build({entryPoints: ['./src/components/pipeline-progress/operation-progress.test.tsx'],
    bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic',
    outfile: '../.test-artifacts/operation-progress.test.cjs',
    plugins: [{name: 'http-boundary', setup(builder) {
        builder.onResolve({filter: /pipelines-thunks$/}, () => ({path: 'commands', namespace: 'test'}));
        builder.onLoad({filter: /.*/, namespace: 'test'}, () => ({resolveDir: process.cwd(), contents: `
            import {createAsyncThunk} from '@reduxjs/toolkit';
            export const stopPipeline = createAsyncThunk('stop', async () => {});
            export const stopAllPipelines = createAsyncThunk('stopAll', async () => {});
        `}));
    }}],
});
execFileSync(process.execPath, ['--test', '../.test-artifacts/operation-progress.test.cjs'], {stdio: 'inherit'});
