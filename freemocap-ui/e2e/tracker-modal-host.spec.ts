import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';
import {readFile, readdir} from 'node:fs/promises';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});

test('streaming toolbar opens a centered tracker dialog and restores the actual host after dismissal', async ({page}, info) => {
    test.setTimeout(60000);
    page.on('pageerror', error => {throw error;});
    const requests: string[] = [];
    await page.route('**/*', route => {
        requests.push(route.request().url());
        return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
    });
    await page.setViewportSize({width:1920,height:1080});
    await page.goto('https://tracker-host.test/');
    const bundle = await build({stdin:{contents:`
        import React from 'react'; import {createRoot} from 'react-dom/client'; import {Provider} from 'react-redux';
        import './src/index.css'; import {store} from './src/store/store';
        import {ServerContext} from './src/services/server/server-context';
        import {StreamingViewPage} from './src/pages/StreamingViewPage';
        const server={connectedCameraIds:[],isConnected:false,isFailed:false};
        function App(){return <React.StrictMode><Provider store={store}><ServerContext.Provider value={server}>
            <div style={{display:'flex',height:'100vh',paddingTop:40,boxSizing:'border-box'}}>
                <aside style={{width:300,flexShrink:0}}>Camera sidebar</aside>
                <main style={{display:'flex',flex:1,minWidth:0,height:'100%'}}><StreamingViewPage/></main>
            </div>
        </ServerContext.Provider></Provider></React.StrictMode>}
        createRoot(document.getElementById('root')).render(<App/>);
    `,resolveDir:resolve('.'),loader:'tsx'},bundle:true,write:false,outdir:'tracker-host-bundle',format:'esm',
        loader:{'.yaml':'text','.svg':'dataurl','.png':'dataurl','.webp':'dataurl','.woff2':'dataurl','.woff':'dataurl','.ttf':'dataurl'},
        alias:{'@':resolve('src')},external:['/images/*','/fonts/*','../images/splashmodal_art.webp','../assets/icons/import-icon.svg'],
        // Only hardware/render leaves are replaced. Production StreamingViewPage,
        // SettingsOverlay, real trigger/state, tracker host, portal, store and CSS run.
        plugins:[{name:'hardware-leaves',setup(builder){
            builder.onResolve({filter:/components\/(camera-views\/CameraViewsGrid|viewport3d\/ThreeJsCanvas)$/},args=>({path:args.path,namespace:'fixture-leaf'}));
            builder.onLoad({filter:/.*/,namespace:'fixture-leaf'},()=>({loader:'tsx',resolveDir:resolve('.'),contents:`import React from 'react';
                export function CameraViewsGrid(){const [clicks,setClicks]=React.useState(0);return <button style={{marginTop:100}} onClick={()=>setClicks(clicks+1)}>Camera view clicks: {clicks}</button>}
                export function ThreeJsCanvas(){return <div>3D viewport</div>}` }));
        }}]});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.css'))){
        await page.addStyleTag({content:output.text});
    }
    // Load the real app stylesheet last: its extraction order previously put
    // the generic mocap rule after tracker sizing, unlike isolated form tests.
    const productionStyles=(await readdir(resolve('dist/assets'))).filter(name=>name.endsWith('.css'));
    expect(productionStyles.length).toBeGreaterThan(0);
    for(const filename of productionStyles) await page.addStyleTag({content:await readFile(resolve('dist/assets',filename),'utf8')});
    for(const output of bundle.outputFiles.filter(output=>!output.path.endsWith('.css'))){
        await page.addScriptTag({content:output.text,type:'module'});
    }
    const trigger=page.getByRole('button',{name:'Skeleton Setup',exact:true});
    const dialog=page.getByRole('dialog',{name:'Skeleton Setup',exact:true});
    const overlay=page.locator('.tracker-dialog-overlay');
    await expect(overlay).toHaveCount(0);
    await trigger.click();
    await expect(dialog).toBeVisible();
    // The window paints its own surface: it was transparent once the classes it borrowed were removed.
    await expect(dialog).not.toHaveCSS('background-color','rgba(0, 0, 0, 0)');
    await expect(dialog).toHaveCSS('border-top-style','solid');
    let box=(await dialog.boundingBox())!;
    expect(box.width).toBe(1200);
    expect(box.x+box.width/2).toBeCloseTo(960);
    expect(box.y+box.height/2).toBeCloseTo(540);
    await expect(dialog.getByRole('button',{name:'Close Skeleton Setup',exact:true})).toBeVisible();
    await dialog.getByRole('combobox',{name:'Skeleton detector',exact:true}).selectOption('dlc');
    await page.screenshot({path:info.outputPath('tracker-host-centered.png'),fullPage:true});
    await dialog.getByRole('button',{name:'Maximize',exact:true}).click();
    await expect(dialog).toHaveCSS('width','1904px');
    await dialog.getByRole('button',{name:'Restore',exact:true}).click();
    await expect(dialog).toHaveCSS('width','1200px');
    const title=dialog.locator('.modal-window-titlebar > span');
    const titleBox=(await title.boundingBox())!;
    await page.mouse.move(titleBox.x+20,titleBox.y+8);
    await page.mouse.down(); await page.mouse.move(titleBox.x+60,titleBox.y+28); await page.mouse.up();
    expect((await dialog.boundingBox())!.x).toBeCloseTo(box.x+40);
    const edge=dialog.getByRole('button',{name:'Resize panel from bottom right edge',exact:true});
    const corner=(await edge.boundingBox())!;
    await page.mouse.move(corner.x+5,corner.y+5); await page.mouse.down();
    await page.mouse.move(corner.x-95,corner.y-95); await page.mouse.up();
    expect((await dialog.boundingBox())!.width).toBeLessThan(1200);
    await page.setViewportSize({width:860,height:720});
    await expect.poll(async()=>{box=(await dialog.boundingBox())!;return box.x+box.width<=852&&box.y+box.height<=712;}).toBe(true);
    await expect(dialog.getByRole('button',{name:'Close Skeleton Setup',exact:true})).toBeInViewport();
    await page.screenshot({path:info.outputPath('tracker-host-compact.png'),fullPage:true});
    await dialog.getByRole('button',{name:'Close Skeleton Setup',exact:true}).click();
    await expect(overlay).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await page.getByRole('button',{name:'Camera view clicks: 0',exact:true}).click();
    await expect(page.getByRole('button',{name:'Camera view clicks: 1',exact:true})).toBeVisible();
    await trigger.click(); await expect(dialog).toBeVisible();
    await page.keyboard.press('Escape'); await expect(overlay).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await trigger.click(); await expect(dialog).toBeVisible();
    await dialog.getByRole('button',{name:'Done',exact:true}).click(); await expect(overlay).toHaveCount(0);
    await trigger.click(); await expect(dialog).toBeVisible();
    await page.mouse.click(2,2); await expect(overlay).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await page.getByRole('button',{name:'Camera view clicks: 1',exact:true}).click();
    await expect(page.getByRole('button',{name:'Camera view clicks: 2',exact:true})).toBeVisible();
    expect(requests.filter(url=>url.includes('/freemocap/')||url.includes('/ws'))).toEqual([]);
    await page.screenshot({path:info.outputPath('tracker-host-closed.png'),fullPage:true});
});
