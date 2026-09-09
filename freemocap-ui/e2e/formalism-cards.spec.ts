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
    await page.getByTitle('About Euler XYZ · degrees').click();
    await expect(page.getByText('Help text',{exact:true})).toBeVisible();
});


