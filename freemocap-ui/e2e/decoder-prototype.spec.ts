import {chromium, expect, test} from '@playwright/test';
import {build} from 'esbuild';
import type {DecoderPrototypeResult} from '../src/services/recording/decoder-prototype';

test('client decoding preserves frame identity through cache access and restart', async () => {
    const bundle = await build({
        entryPoints: ['src/services/recording/decoder-prototype.ts'],
        bundle: true, write: false, format: 'iife', globalName: 'decoderPrototype',
    });
    const browser = await chromium.launch({channel: 'msedge', headless: true});
    try {
        const page = await browser.newPage();
        await page.route('https://decoder.test/', route => route.fulfill({contentType: 'text/html', body: '<!doctype html><title>Decoder test</title>'}));
        await page.goto('https://decoder.test/');
        await page.addScriptTag({content: bundle.outputFiles[0].text});
        const result = await page.evaluate(async (): Promise<DecoderPrototypeResult> => {
            const prototype = globalThis as typeof globalThis & {
                decoderPrototype: {runDecoderPrototype: () => Promise<DecoderPrototypeResult>};
            };
            return prototype.decoderPrototype.runDecoderPrototype();
        });
        expect(result).toEqual({codec: 'vp8', decodedFrames: 24, cacheHits: 4,
            cacheBytes: 64 * 48 * 4 * 8, restartVerified: true});
    } finally { await browser.close(); }
});
