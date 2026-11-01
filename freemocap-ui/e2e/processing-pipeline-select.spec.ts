import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});
test('processing selector offers the graph and an unavailable custom pipeline', async ({page}) => {
    await page.route('**/*', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('https://pipeline-settings.test/');
    const bundle = await build({stdin: {contents: `
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import ProcessingPipelineSelect from './src/components/mocap-setup/processing-pipeline-select';
        createRoot(document.getElementById('root')).render(<ProcessingPipelineSelect />);
    `, resolveDir: resolve('.'), loader: 'tsx'}, bundle: true, write: false, format: 'esm', alias: {'@': resolve('src')}});
    await page.addScriptTag({content: bundle.outputFiles[0].text, type: 'module'});
    await page.getByRole('button', {name: 'Typed data flow graph V1'}).click();
    await expect(page.getByRole('option')).toHaveCount(2);
    await expect(page.getByRole('option', {name: 'Typed data flow graph V1'})).toHaveAttribute('aria-selected', 'true');
    const custom = page.getByRole('option', {name: 'Add custom pipeline…'});
    await expect(custom).toHaveAttribute('aria-disabled', 'true');
    await custom.locator('.button-sm-group').hover();
    await expect(page.getByRole('tooltip')).toHaveText('Coming soon');
    await expect(custom.getByRole('button')).toBeDisabled();
    await page.getByRole('button', {name: 'Typed data flow graph V1'}).click();
    await expect(page.getByRole('listbox')).toHaveCount(0);
});
