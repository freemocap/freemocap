import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test('Escape cancels a numeric edit without applying it; Enter applies the next edit', async ({page}) => {
    await page.route('https://numeric-edit.test/', route => route.fulfill({
        contentType: 'text/html', body: '<div id="root"></div>',
    }));
    await page.goto('https://numeric-edit.test/');
    const bundle = await build({stdin: {contents: `
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import ValueSelector from './src/components/ui-components/ValueSelector';
        function App() {
            const [value, setValue] = React.useState(5);
            const [changes, setChanges] = React.useState(0);
            return <><ValueSelector ariaLabel="Threshold" value={value} min={0} max={10}
                onChange={next => {setValue(next); setChanges(count => count + 1);}}/>
                <output>{value}:{changes}</output></>;
        }
        createRoot(document.getElementById('root')).render(<App/>);
    `, resolveDir: resolve('.'), loader: 'tsx'}, bundle: true, write: false,
        format: 'iife', alias: {'@': resolve('src')}});
    await page.addScriptTag({content: bundle.outputFiles[0].text});
    const input = page.getByRole('spinbutton', {name: 'Threshold'});
    await input.fill('9');
    await input.press('Escape');
    await expect(input).toHaveValue('5');
    await expect(page.locator('output')).toHaveText('5:0');
    await input.fill('7');
    await input.press('Enter');
    await expect(input).toHaveValue('7');
    await expect(page.locator('output')).toHaveText('7:1');
});
