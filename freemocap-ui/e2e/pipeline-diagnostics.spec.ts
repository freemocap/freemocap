import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {readFile} from 'node:fs/promises';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('backend diagnostic frame is self-contained and resets on disconnect', async ({page}) => {
    page.on('pageerror', error => {throw error;});
    const bytes = [...await readFile('e2e/fixtures/diagnostics.bin')];
    await page.setContent('<output id="result"></output>');
    const bundle = await build({
        stdin: {contents: `
            import {TransportService} from './src/services/server/transport/TransportService';
            function assert(value: boolean, message: string): void {if (!value) throw new Error(message);}
            const bytes = new Uint8Array(${JSON.stringify(bytes)});
            for (let connection = 0; connection < 2; connection++) {
                const transport = new TransportService({url: 'ws://unused'});
                let deliveries = 0;
                transport.subscribeToDiagnostics(frame => {deliveries++;});
                (transport as unknown as {dispatchBytes(buffer: ArrayBuffer): void}).dispatchBytes(bytes.buffer);
                const frame = transport.getLatestDiagnostics();
                assert(frame?.frameNumber === 42, 'Frame identity lost');
                const block = frame!.values!.reprojection[0];
                assert(block.source_ids[0] === 'camera-a' && block.point_names[0] === 'body.nose', 'Diagnostic axes lost');
                const data = new DataView(block.data.buffer, block.data.byteOffset, block.data.byteLength);
                assert(data.getFloat32(0, true) === 2, 'Error value changed');
                assert(Number.isNaN(data.getFloat32(16, true)), 'Missing error became zero');
                assert(frame!.values!.rigid_body.human.arm.residual === 5, 'Rigid residual lost');
                assert(frame!.values!.rigid_body.human.leg.residual === undefined, 'Missing length became zero');
                transport.reset();
                assert(transport.getLatestDiagnostics() === null && deliveries === 2, 'Disconnect retained diagnostic state');
            }
            document.getElementById('result')!.textContent = 'passed';
        `, resolveDir: path.resolve('.'), loader: 'ts'},
        bundle: true, write: false, format: 'esm', alias: {'@': path.resolve('src')},
        plugins: [{name: 'socket', setup(builder) {
            builder.onLoad({filter: /websocket-connection\.ts$/}, () => ({contents: `
                export const ConnectionState = {};
                export class WebSocketConnection {on(): void {}}
            `, loader: 'ts'}));
        }}],
    });
    await page.addScriptTag({content: bundle.outputFiles[0].text, type: 'module'});
    await expect(page.locator('#result')).toHaveText('passed');
});
