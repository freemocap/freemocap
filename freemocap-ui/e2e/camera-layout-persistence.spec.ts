import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});

test('camera grid preserves dragged positions when the same camera list is republished', async ({page}) => {
    await page.route('http://localhost:53117/', route => route.fulfill({
        contentType: 'text/html', body: '<div id="root" style="width:800px;height:600px"></div>',
    }));
    await page.goto('http://localhost:53117/');
    const bundle = await build({stdin: {contents: `
        import React, {useState} from 'react';
        import {createRoot} from 'react-dom/client';
        import {useGridLayout} from './src/hooks/useGridLayout';
        function CameraGridProbe() {
            const [cameraIds, setCameraIds] = useState(['3e59', '7599', '8752']);
            const [resetKey, setResetKey] = useState(0);
            const grid = useGridLayout({itemIds:cameraIds, manualColumns:3, resetKey});
            window.gridProbe = {
                layout:grid.layout,
                republish:()=>setCameraIds([...cameraIds]),
                removeCamera:()=>setCameraIds(cameraIds.slice(0,2)),
                reset:()=>setResetKey(resetKey+1),
                swap:()=>{
                    grid.gridHandlers.onDragStart();
                    const [first,second] = grid.layout;
                    grid.gridHandlers.onDragStop(grid.layout, first, {...first,x:second.x,y:second.y});
                },
            };
            return <div ref={grid.containerRef}/>;
        }
        createRoot(document.getElementById('root')).render(<CameraGridProbe/>);
    `, resolveDir:path.resolve('.'), loader:'tsx'}, bundle:true, write:false, format:'esm',
        jsx:'automatic', alias:{'@':path.resolve('src')}});
    await page.addScriptTag({type:'module', content:bundle.outputFiles[0].text});
    const positions = () => page.evaluate(() => (window as any).gridProbe?.layout.map(({i,x,y}:any) => ({i,x,y})));
    await expect.poll(positions).toHaveLength(3);
    const original = await positions();
    await page.evaluate(() => (window as any).gridProbe.swap());
    await expect.poll(positions).not.toEqual(original);
    const dragged = await positions();
    await page.evaluate(() => (window as any).gridProbe.republish());
    // Wait for the render and its reset effect, not just the synchronous state update.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    expect(await positions()).toEqual(dragged);
    await page.evaluate(() => (window as any).gridProbe.reset());
    await expect.poll(positions).toEqual(original);
    await page.evaluate(() => (window as any).gridProbe.removeCamera());
    await expect.poll(positions).toHaveLength(2);
});
