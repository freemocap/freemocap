import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('modal drag, edge resize, maximize and restore work in StrictMode', async ({page}) => {
    const bundle = await build({
        stdin: {contents: `import React from 'react'; import {createRoot} from 'react-dom/client'; import ModalWindowControls from './src/components/ui-components/ModalWindowControls'; createRoot(document.getElementById('root')).render(<React.StrictMode><div style={{position:'fixed',left:100,top:100,width:500,height:400}}><ModalWindowControls title="Test modal"/><div>Content</div></div></React.StrictMode>);`, resolveDir: path.resolve('.'), loader: 'tsx'},
        bundle: true, write: false, outdir: 'modal-test-bundle', jsx: 'automatic',
    });
    await page.setViewportSize({width: 1280, height: 900});
    await page.setContent('<div id="root"></div>');
    for (const output of bundle.outputFiles) {
        if (output.path.endsWith('.css')) await page.addStyleTag({content: output.text});
        else await page.addScriptTag({content: output.text});
    }
    const modal = page.getByRole('dialog', {name: 'Test modal'});
    const initial = await modal.boundingBox();
    expect(initial).not.toBeNull();
    await page.getByTitle('Maximize window').click();
    await expect(modal).toHaveCSS('width', '1264px');
    await page.getByTitle('Restore window size').click();
    await expect(modal).toHaveCSS('width', `${initial!.width}px`);
    const title = await page.getByText('Test modal', {exact: true}).boundingBox();
    await page.mouse.move(title!.x + 10, title!.y + 10);
    await page.mouse.down(); await page.mouse.move(title!.x + 60, title!.y + 40); await page.mouse.up();
    expect((await modal.boundingBox())!.x).toBeCloseTo(initial!.x + 50);
    const edge = await page.getByRole('button', {name: 'Resize panel from right edge', exact: true}).boundingBox();
    await page.mouse.move(edge!.x + 2, edge!.y + 30);
    await page.mouse.down(); await page.mouse.move(edge!.x + 102, edge!.y + 30); await page.mouse.up();
    expect((await modal.boundingBox())!.width).toBeGreaterThan(initial!.width);
});

