// Serve this package's files for the browser bundle check:
//   node tools/serve-static.mjs [port]   then open /tests/browser/bundle-check.html
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {extname, join, normalize, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const types = {'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.map':'application/json'};
const port = Number(process.argv[2] ?? 8790);
createServer(async (request, response) => {
 const path = normalize(join(root, decodeURIComponent(new URL(request.url, 'http://local').pathname)));
 if (!path.startsWith(root.endsWith(sep) ? root : root + sep)) { response.writeHead(403).end(); return; }
 try {
  const body = await readFile(path);
  response.writeHead(200, {'content-type': `${types[extname(path)] ?? 'application/octet-stream'}; charset=utf-8`}).end(body);
 } catch { response.writeHead(404).end(); }
}).listen(port, '127.0.0.1', () => console.log(`Serving ${root} at http://127.0.0.1:${port}/`));
