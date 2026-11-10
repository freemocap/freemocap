import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});

// The production StreamingViewPage, toolbar, menus, store and stylesheets run. Only
// the camera grid and the WebGL canvas are replaced; the canvas stub keeps the
// production viewport root and its top-left panel, whose z-index used to paint
// over every toolbar menu.
test('processing settings paint above the viewport and close without disturbing it', async ({page}) => {
    test.setTimeout(60000);
    page.on('pageerror', error => {throw error;});
    await page.route('**/*', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    // No outputs or protocols on this server; registered last, so it runs first.
    await page.route('**/freemocap/streaming/**', route => route.fulfill({json: []}));
    await page.setViewportSize({width: 1600, height: 1000});
    await page.goto('https://toolbar-menus.test/');
    const bundle = await build({stdin: {contents: `
        import React from 'react'; import {createRoot} from 'react-dom/client'; import {Provider} from 'react-redux';
        import './src/index.css'; import './src/components/viewport3d/scene/viewport-overlay.css';
        import {store} from './src/store/store';
        import {ServerContext} from './src/services/server/server-context';
        import {StreamingViewPage} from './src/pages/StreamingViewPage';
        const server={connectedCameraIds:[],isConnected:false,isFailed:false};
        createRoot(document.getElementById('root')).render(<Provider store={store}><ServerContext.Provider value={server}>
            <main style={{display:'flex',height:'100vh',paddingTop:40,boxSizing:'border-box'}}><StreamingViewPage/></main>
        </ServerContext.Provider></Provider>);
    `, resolveDir: resolve('.'), loader: 'tsx'}, bundle: true, write: false, outdir: 'toolbar-menus-bundle', format: 'esm',
        loader: {'.yaml': 'text', '.svg': 'dataurl', '.png': 'dataurl', '.webp': 'dataurl', '.woff2': 'dataurl', '.woff': 'dataurl', '.ttf': 'dataurl'},
        alias: {'@': resolve('src')}, external: ['/images/*', '/fonts/*', '../images/splashmodal_art.webp', '../assets/icons/import-icon.svg'],
        plugins: [{name: 'render-leaves', setup(builder) {
            builder.onResolve({filter: /components\/(camera-views\/CameraViewsGrid|viewport3d\/ThreeJsCanvas)$/}, args => ({path: args.path, namespace: 'fixture-leaf'}));
            builder.onLoad({filter: /.*/, namespace: 'fixture-leaf'}, () => ({loader: 'tsx', resolveDir: resolve('.'), contents: `import React from 'react';
                export function CameraViewsGrid(){return <div>Camera grid</div>}
                // An expanded Viewport panel, wide enough to sit under both menus.
                export function ThreeJsCanvas(){return <div className="3d-viewport-container vp-root pos-rel w-full h-full">
                    <section className="vp-layers" style={{width:600,height:300}}><button>Viewport</button></section></div>}`}));
        }}]});
    for (const output of bundle.outputFiles.filter(output => output.path.endsWith('.css'))) await page.addStyleTag({content: output.text});
    for (const output of bundle.outputFiles.filter(output => !output.path.endsWith('.css'))) await page.addScriptTag({content: output.text, type: 'module'});
    await expect(page.locator('.vp-layers')).toBeVisible();

    for (const [name, menuSelector] of [['Processing settings', '.tracker-settings-modal']]) {
        const trigger = page.getByRole('button', {name, exact: true});
        await trigger.click();
        const menu = page.locator(menuSelector);
        await expect(menu).toBeVisible();
        // A menu button keeps focus after opening; its hint must not cover the menu.
        await expect(page.locator('.tooltip-surface:popover-open')).toHaveCount(0);
        const drawnOnTop = await page.evaluate(selector => {
            const menuElement = document.querySelector(selector)!;
            const a = menuElement.getBoundingClientRect(), b = document.querySelector('.vp-layers')!.getBoundingClientRect();
            const left = Math.max(a.left, b.left), right = Math.min(a.right, b.right);
            const top = Math.max(a.top, b.top), bottom = Math.min(a.bottom, b.bottom);
            const box = (r: DOMRect) => [r.left, r.top, r.right, r.bottom].map(Math.round).join(',');
            if (left >= right || top >= bottom) return `no overlap: menu ${box(a)} viewport panel ${box(b)}`;
            return menuElement.contains(document.elementFromPoint((left + right) / 2, (top + bottom) / 2));
        }, menuSelector);
        expect(drawnOnTop).toBe(true);
        await menu.getByRole('button', {name: 'Done', exact: true}).click();
        await expect(menu).toHaveCount(0);
        await expect(trigger).toBeFocused();
    }
});
