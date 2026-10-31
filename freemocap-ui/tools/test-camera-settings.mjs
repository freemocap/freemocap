import {build} from 'esbuild';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const output = path.resolve(process.argv[2]);
await build({entryPoints:['src/store/slices/cameras/camera-server-settings.test.ts'],
    bundle:true,platform:'node',format:'cjs',outfile:output,loader:{'.yaml':'text'},
    define:{'import.meta.env':'{}','import.meta.url':'""'},
    // The store's browser barrel initializes an unused image-decoder canvas.
    // These reducer tests never draw; the hardware UI campaign tests real canvases.
    banner:{js:'globalThis.OffscreenCanvas=class { getContext() { return {}; } };'}});
await import(pathToFileURL(output).href);
