import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('accept preserves a transform; cancel and reset remain draft edits', async ({page}) => {
    const bundle = await build({
        stdin: {contents: `import React, {useState} from 'react';
            import {createRoot} from 'react-dom/client';
            import {Matrix4} from 'three';
            import Editor from './src/components/mocap-setup/transform-editor';
            function App() {
                const [saved, save] = useState(() => new Matrix4());
                const [open, setOpen] = useState(false);
                return <><button onClick={() => setOpen(true)}>Define transformation</button>
                    <output>{saved.elements[12]}</output>
                    {open && <Editor initialMatrix={saved} onClose={() => setOpen(false)}
                        onAccept={matrix => {save(matrix); setOpen(false);}}/>}</>;
            }
            createRoot(document.getElementById('root')).render(<App/>);`,
            resolveDir: path.resolve('.'), loader: 'tsx'},
        bundle: true, write: false, outdir: 'transform-test-bundle', jsx: 'automatic',
        alias: {'@': path.resolve('src')},
        plugins: [{name: 'omit-webgl-preview', setup(builder) {
            builder.onLoad({filter: /transform-preview\.tsx$/}, () => ({
                contents: 'export default function Preview() { return null; }', loader: 'tsx',
            }));
        }}],
    });
    await page.setContent('<div id="root"></div>');
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text});
    }
    const open = page.getByRole('button', {name: 'Define transformation', exact: true});
    const input = page.getByRole('textbox', {name: 'Position: X mm', exact: true});
    await open.click();
    await input.click();
    await input.fill('123.456');
    await page.getByRole('button', {name: 'Accept transformation', exact: true}).click();
    await expect(page.locator('output')).toHaveText('123.456');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await open.click();
    await expect(input).toHaveValue('123.456');
    await page.getByRole('button', {name: 'Reset to identity', exact: true}).click();
    await expect(input).toHaveValue('0');
    await page.getByRole('button', {name: 'Cancel', exact: true}).click();
    await open.click();
    await expect(input).toHaveValue('123.456');
});
