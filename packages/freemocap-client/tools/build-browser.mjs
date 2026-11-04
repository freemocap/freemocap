// One self-contained, minified ES module for pages without a bundler: dependencies
// are inlined, so `<script type="module">` can import it from any static server.
// The source map keeps DevTools readable.
import {build} from 'esbuild';
await build({
 entryPoints:['src/index.ts'],bundle:true,format:'esm',platform:'browser',target:'es2022',
 outfile:'dist/browser/freemocap-client.js',minify:true,sourcemap:true,legalComments:'eof',
});
