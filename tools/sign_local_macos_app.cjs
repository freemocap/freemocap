#!/usr/bin/env node
// Local ad-hoc signing only. Release builds use Developer ID and notarization in CI.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {signAsync} = require('../freemocap-ui/node_modules/@electron/osx-sign');

async function main() {
    if (process.platform !== 'darwin' || process.argv.length !== 3) {
        throw new Error('Usage on macOS: node tools/sign_local_macos_app.cjs /path/to/FreeMoCap.app');
    }
    const app = path.resolve(process.argv[2]);
    if (!app.endsWith('.app') || !fs.existsSync(path.join(app, 'Contents', 'Info.plist'))) {
        throw new Error(`Expected an existing macOS application bundle: ${app}`);
    }
    const entitlements = path.resolve(__dirname, '../freemocap-ui/entitlements.mac.plist');
    await signAsync({
        app,
        identity: '-',
        identityValidation: false,
        preAutoEntitlements: false,
        preEmbedProvisioningProfile: false,
        gatekeeperAssess: false,
        optionsForFile: () => ({entitlements, hardenedRuntime: true, timestamp: 'none'}),
    });
    execFileSync('/usr/bin/codesign', ['--verify', '--deep', '--strict', '--verbose=2', app], {stdio: 'inherit'});
    const plist = execFileSync('/usr/bin/codesign', ['-d', '--entitlements', ':-', app], {encoding: 'utf8'});
    const applied = JSON.parse(execFileSync('/usr/bin/plutil', ['-convert', 'json', '-o', '-', '-'],
        {input: plist, encoding: 'utf8'}));
    if (applied['com.apple.security.device.camera'] !== true) throw new Error('Signed bundle is missing the camera entitlement');
    console.log(`Signed and verified for local testing: ${app}`);
}

main().catch(error => {console.error(error); process.exitCode = 1;});
