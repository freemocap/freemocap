import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer, type Server} from 'node:http';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});
let server: Server;
let url: string;
test.beforeAll(async () => {
    const fixture = resolve('e2e/fixtures/reconstruction-settings.tsx');
    const bundle = await build({entryPoints: [fixture], bundle: true, write: false,
        format: 'esm', platform: 'browser', jsx: 'automatic', loader: {'.css': 'empty'}, alias: {
            '@/hooks/useRealtimePipelineSync': fixture, '@/hooks/useMocap': fixture,
            '@/store/slices/mocap': fixture, '@': resolve('src'),
        }});
    server = createServer((request, response) => {
        response.setHeader('Content-Type', request.url === '/entry.js' ? 'text/javascript' : 'text/html');
        response.end(request.url === '/entry.js' ? bundle.outputFiles[0].text
            : '<div id="root"></div><script type="module" src="/entry.js"></script>');
    });
    await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
    url = `http://127.0.0.1:${(server.address() as any).port}`;
});
test.afterAll(async () => {
    if (server) await new Promise<void>(done => {server.close(() => done()); server.closeAllConnections();});
});

for (const panel of ['capture', 'pipeline']) {
    test(`${panel} Skeleton switch controls the backend reconstruction flag`, async ({page}) => {
        await page.goto(`${url}?${panel}`);
        const toggle = page.locator('.toggle-button').filter({has: page.getByText('Skeleton', {exact: true})});
        await expect(toggle).toBeVisible();
        // Start from the shipped defaults, turn the control off, then on.
        await toggle.click();
        await expect.poll(() => page.evaluate(() => (window as any).appliedConfig?.aggregator_config.skeleton_fitting_enabled)).toBe(false);
        await toggle.click();
        await expect.poll(() => page.evaluate(() => (window as any).appliedConfig?.aggregator_config.skeleton_fitting_enabled)).toBe(true);
        expect(await page.evaluate(() => 'skeleton_enabled' in (window as any).appliedConfig.aggregator_config)).toBe(false);
    });
}
