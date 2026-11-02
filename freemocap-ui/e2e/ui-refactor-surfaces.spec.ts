import {test,expect,_electron as electron} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import path from 'node:path';
const url=process.env.UI_HARNESS_URL || 'http://127.0.0.1:7777';
for (const route of ['streaming','playback','active-recording']) {
  test(`main surface ${route}`,async({page},info)=>{
    const errors:string[]=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.clock.setFixedTime(new Date('2026-11-02T17:00:00-05:00'));
    await page.routeWebSocket(/.*/,socket=>socket.close());
    await page.addInitScript(()=>sessionStorage.setItem('freemocap.welcomeShown','true'));
    await page.goto(`${url}/#/${route}`);
    await expect(page.locator('#root')).not.toBeEmpty();
    await page.evaluate(()=>document.fonts.ready);
    await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
    await expect.soft(page).toHaveScreenshot(`screen-${route}.png`,{animations:'disabled'});
    const contrast=await new AxeBuilder({page}).withRules(['color-contrast']).analyze();
    await info.attach('contrast',{body:JSON.stringify({violations:contrast.violations,incomplete:contrast.incomplete},null,2),contentType:'application/json'});
    expect.soft(errors,'Uncaught application errors').toEqual([]);
    expect.soft(contrast.violations,'Text contrast violations; see attachment').toEqual([]);
  });
}
test('Electron starts and renders the application',async({},info)=>{
  const start=performance.now();
  const app=await electron.launch({args:[path.resolve('dist-electron/main/index.js'),`--user-data-dir=${info.outputPath('electron-profile')}`],env:{...process.env,NODE_ENV:'development',VITE_DEV_SERVER_URL:url}});
  try {
    const page=await app.firstWindow();
    await expect(page.locator('#root')).not.toBeEmpty();
    await page.evaluate(()=>document.fonts.ready);
    await info.attach('startup',{body:JSON.stringify({milliseconds:performance.now()-start,definition:'Electron launch to nonempty React root and fonts ready; backend not included'}),contentType:'application/json'});
    await page.screenshot({path:info.outputPath('electron-startup.png')});
  } finally {await app.close();}
});
