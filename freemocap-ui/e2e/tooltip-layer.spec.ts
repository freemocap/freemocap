import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL ?? 'msedge', viewport: {width: 800, height: 600}});

test.beforeEach(async ({page}) => {
    const root = process.cwd();
    const bundle = await build({bundle: true, write: false, format: 'iife', platform: 'browser',
        absWorkingDir: root, alias: {'@': resolve(root, 'src')},
        stdin: {resolveDir: root, loader: 'tsx', contents: `
            import React from 'react'; import {createRoot} from 'react-dom/client';
            import AnchoredInfo from './src/components/ui-components/AnchoredInfo';
            import ButtonSm from './src/components/ui-components/ButtonSm';
            import IconButton from './src/components/ui-components/IconButton';
            createRoot(document.getElementById('root')).render(<React.StrictMode>
                <div id="clip" style={{position:'absolute',left:100,top:200,width:180,height:35,overflow:'hidden',transform:'translateZ(0)'}}>
                    <ButtonSm text="Hover me" tooltip tooltipText="Button help outside the clipped parent"/>
                    <IconButton icon="test" ariaLabel="Disabled control" disabled tooltip tooltipText="Disabled help"/>
                </div>
                <div id="edge" style={{position:'absolute',right:8,top:8}}>
                    <AnchoredInfo title="Setup help" text={<><p>{'Long setup instructions. '.repeat(35)}</p><button>Help action</button></>}/>
                </div>
                <div id="cover" style={{position:'absolute',left:80,top:240,width:500,height:180,background:'red',zIndex:2147483647}}/>
            </React.StrictMode>);
        `}});
    await page.setContent('<div id="root"></div>');
    await page.addStyleTag({content: readFileSync(resolve(root, 'src/styles/tooltips.css'), 'utf8') + `
        body{font:14px sans-serif;margin:0}button{padding:4px}p{margin:4px}
        .pos-rel{position:relative}.flex{display:flex}.flex-col{flex-direction:column}
        .icon-button{width:28px;height:28px}.bg-dark{background:#222;color:white}
    `});
    await page.addScriptTag({content: bundle.outputFiles[0].text});
});

test('button help escapes overflow and paints above a covering panel', async ({page}) => {
    await page.getByRole('button', {name: 'Hover me'}).hover();
    const tip = page.locator('.tooltip-container').filter({hasText: 'Button help outside'});
    await expect(tip).toBeVisible();
    await expect.poll(() => tip.evaluate(el => {
        const r = el.getBoundingClientRect();
        // Temporarily enable hit testing to verify actual paint order, not just DOM visibility.
        const previous = (el as HTMLElement).style.pointerEvents;
        (el as HTMLElement).style.pointerEvents = 'auto';
        const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        (el as HTMLElement).style.pointerEvents = previous;
        return el.contains(hit);
    })).toBe(true);
});

test('pinned info stays within the viewport and long help remains reachable', async ({page}, testInfo) => {
    await page.getByRole('button', {name: 'Setup help'}).click();
    const tip = page.locator('.prompt-tooltip-container');
    await expect(tip).toBeVisible();
    await expect.poll(() => tip.evaluate(el => {
        const r = el.getBoundingClientRect();
        return r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight;
    })).toBe(true);
    await page.getByRole('button', {name: 'Help action'}).click();
    await page.setViewportSize({width: 360, height: 300});
    await expect.poll(() => tip.evaluate(el => {
        const r = el.getBoundingClientRect();
        return r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight;
    })).toBe(true);
    await page.screenshot({path: testInfo.outputPath('tooltip-small-window.png')});
    await page.keyboard.press('Escape');
    await expect(tip).toHaveCount(0);
    await page.getByRole('button', {name: 'Setup help'}).click();
    await expect(tip).toBeVisible();
    await tip.locator('.icon-button-holder button').click();
    await expect(tip).toHaveCount(0);
});

test('disabled icon hints support hover, keyboard focus and Escape', async ({page}) => {
    const wrapper = page.locator('.tooltip-wrapper');
    // Keep this fixture's disabled control on the first row of the clipped panel.
    await page.locator('#clip').evaluate(el => {el.style.width = '400px'; el.style.display = 'flex';});
    const tip = page.locator('.tooltip-container').filter({hasText: 'Disabled help'});
    await wrapper.hover();
    await expect(tip).toBeVisible();
    await page.mouse.move(20, 20);
    await expect(tip).toBeHidden();
    await wrapper.focus();
    await expect(tip).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(tip).toBeHidden();
    await page.getByRole('button', {name: 'Hover me'}).focus();
    await wrapper.focus();
    await expect(tip).toBeVisible();
});

test('help opened inside a modal paints above the modal and follows its anchor', async ({page}) => {
    await page.evaluate(() => {
        const dialog = document.createElement('dialog');
        document.body.append(dialog);
        dialog.append(document.querySelector('#clip')!);
        dialog.style.cssText = 'width:600px;height:400px;overflow:hidden;';
        dialog.showModal();
    });
    const button = page.getByRole('button', {name: 'Hover me'});
    await button.focus();
    const tip = page.locator('.tooltip-container').filter({hasText: 'Button help outside'});
    await expect(tip).toBeVisible();
    expect(await tip.evaluate(el => el.matches(':popover-open'))).toBe(true);
    const initial = await tip.boundingBox();
    await page.locator('#clip').evaluate(el => {el.style.top = '100px';});
    await expect.poll(async () => (await tip.boundingBox())!.y).toBeLessThan(initial!.y - 50);
});
