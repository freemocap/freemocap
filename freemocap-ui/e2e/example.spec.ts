import {test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';

test('production UI connects to its owned backend and closes cleanly', async ({}, info) => {
    test.setTimeout(240_000);
    // The old scaffold checked a Vite demo title and overwrote a tracked image.
    // Use the application's existing observer and its isolated server lifecycle.
    await promisify(execFile)(process.env.FREEMOCAP_TEST_PYTHON ?? resolve('../.venv/Scripts/python.exe'),
        ['-B', '-m', 'freemocap.tools.hardware_validation', 'ui-idle', '--output', info.outputPath('application')],
        {cwd: resolve('..'), windowsHide: true, timeout: 230_000});
});
