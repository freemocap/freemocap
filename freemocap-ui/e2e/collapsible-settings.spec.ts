import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

for (const component of ['sidebar', 'processing']) {
test(`${component} settings retain mounted state and support keyboard expansion`, async ({page}) => {
    const bundle = await build({stdin: {contents: `
        import React, {useEffect, useState} from 'react';
        import {createRoot} from 'react-dom/client';
        ${component === 'sidebar'
            ? "import {CollapsibleSidebarSection as Section} from './src/components/common/CollapsibleSidebarSection';"
            : "import Section from './src/components/common/settings-layout/settings-section';"}
        let mounts = 0;
        function Settings() {
            const [value, setValue] = useState('');
            useEffect(() => {document.getElementById('mounts').textContent = String(++mounts)}, []);
            return <input aria-label="Definition" value={value} onChange={e => setValue(e.target.value)}/>;
        }
        createRoot(document.getElementById('root')).render(<Section title="Camera geometry" ${component === 'sidebar' ? 'icon={null} keepMounted' : 'defaultExpanded={false}'}><Settings/></Section>);
        `, resolveDir: path.resolve('.'), loader: 'tsx'}, bundle: true, write: false, outdir: 'settings-test-bundle', jsx: 'automatic'});
    await page.setContent('<output id="mounts"></output><div id="root"></div>');
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text});
    }
    const header = page.getByRole('button', {name: 'Camera geometry'});
    await expect(page.locator('#mounts')).toHaveText('1');
    await expect(page.getByLabel('Definition')).toBeHidden();
    await header.focus();
    await header.press('Enter');
    await page.getByLabel('Definition').fill('accepted transform');
    await header.click();
    await expect(page.getByLabel('Definition')).toBeHidden();
    await header.press('Space');
    await expect(page.getByLabel('Definition')).toHaveValue('accepted transform');
    await expect(page.locator('#mounts')).toHaveText('1');
});
}
