import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';
test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('formalism cards synchronize accepted edits and reject invalid transforms', async ({page}) => {
    const bundle = await build({stdin: {contents: `import './src/styles/tooltips.css'; import React, {useState} from 'react'; import {createRoot} from 'react-dom/client'; import {Matrix4} from 'three'; import Card from './src/components/mocap-setup/formalism-card'; import {TransformRepresentation as R} from './src/components/mocap-setup/reference-transform'; function App(){const [matrix,setMatrix]=useState(()=>new Matrix4());return <><Card title="Position" help="Position units" representation={R.Euler} indices={[0,1,2]} matrix={matrix} onChange={setMatrix}/>{Object.values(R).map(r=><Card key={r} title={r} help="Help text" representation={r} indices={r===R.Matrix?Array.from({length:16},(_,i)=>i):r===R.Euler?[0,1,2,3,4,5]:[0,1,2,3,4,5,6]} matrix={matrix} onChange={setMatrix}/>)}</>} createRoot(document.getElementById('root')).render(<App/>);`,resolveDir:path.resolve('.'),loader:'tsx'},bundle:true,write:false,outdir:'formalism-test-bundle',jsx:'automatic',alias:{'@':path.resolve('src')}});
    await page.setContent('<div id="root"></div>');
    for(const file of bundle.outputFiles) {
        if(file.path.endsWith('.css')) await page.addStyleTag({content:file.text});
        else await page.addScriptTag({content:file.text});
    }
    const translation=page.getByRole('textbox',{name:'Euler XYZ · degrees: X mm',exact:true});
    await translation.click(); await translation.fill('123.456'); await translation.press('Enter');
    await expect(page.getByRole('textbox',{name:'4×4 matrix · row major: Row 1, column 4',exact:true})).toHaveValue('123.456');
    await page.getByRole('button', {name: 'm', exact: true}).click();
    const metres = page.getByRole('textbox', {name: 'Position: X m', exact: true});
    await expect(metres).toHaveValue('0.123456');
    await metres.click(); await metres.fill('2.5'); await metres.press('Enter');
    await expect(translation).toHaveValue('2500');
    const invalid=page.getByRole('textbox',{name:'4×4 matrix · row major: Row 1, column 1',exact:true});
    await invalid.click(); await invalid.fill('2'); await invalid.press('Enter');
    await expect(invalid).toHaveValue('1');
    await expect(page.getByRole('alert')).toContainText('Not applied');
    await expect(translation).toHaveValue('2500');
    const help = page.getByRole('button', {name: 'About Euler XYZ · degrees', exact: true});
    await help.hover();
    await expect(help).not.toHaveAttribute('title');
    await expect(page.getByText('Help text', {exact: true})).toBeVisible();
    await expect(page.locator('.prompt-tooltip-reference-container')).toHaveCSS('z-index', '10000');
    await page.mouse.move(1200, 700);
    await expect(page.getByText('Help text', {exact: true})).toHaveCount(0);
    await help.click();
    await page.mouse.move(1200, 700);
    await expect(page.getByText('Help text',{exact:true})).toBeVisible();
    await page.mouse.click(1200, 700);
    const popup = page.locator('.prompt-tooltip-container');
    await expect(popup).toBeVisible();
    const heading = popup.locator('h3');
    await expect(popup).toHaveCSS('cursor', 'grab');
    await heading.hover();
    const before = await heading.boundingBox();
    if (!before) throw new Error('Pinned help heading has no bounds');
    await page.mouse.move(before.x + 10, before.y + 10);
    await page.mouse.down();
    await page.mouse.move(before.x + 90, before.y + 50, {steps: 5});
    await page.mouse.up();
    const after = await heading.boundingBox();
    if (!after) throw new Error('Dragged help heading has no bounds');
    expect(after.x - before.x).toBeCloseTo(80, 0);
    expect(after.y - before.y).toBeCloseTo(40, 0);
    await popup.locator('button').click();
    await expect(popup).toHaveCount(0);
});




