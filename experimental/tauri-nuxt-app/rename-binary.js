import { execa } from 'execa';
import * as fs from 'fs';

let extension = ''
if (process.platform === 'win32') {
    extension = '.exe'
}

async function main() {
    const baseName = 'dist/main';
    const rustInfo = (await execa('rustc', ['-vV'])).stdout
    const targetTriple = /host: (\S+)/g.exec(rustInfo)[1]
    if (!targetTriple) {
        console.error('Failed to determine platform target triple')
    }
    fs.renameSync(
        `${baseName}${extension}`,
        `${baseName}-${targetTriple}${extension}`
    )
    console.log(`Renamed binary to sidecar-${targetTriple}${extension}`)
}

main().catch((e) => {
    throw e
})