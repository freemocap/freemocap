import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test('processing control remains usable after failure, edited settings, reconnect and late responses', async ({page}) => {
    test.setTimeout(60000);
    page.on('pageerror', error => {throw error;});
    const requests: any[] = [];
    let release: (() => Promise<void>) | undefined;
    await page.route('**/*', async route => {
        if (route.request().method() === 'OPTIONS') return route.fulfill({status:204,
            headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}});
        if (!route.request().url().includes('/freemocap/realtime/apply')) {
            return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
        }
        const body = route.request().postDataJSON();
        requests.push(body);
        const reply = (status: number, value: unknown) => route.fulfill({status,
            headers:{'Access-Control-Allow-Origin':'*'}, json:value});
        if (requests.length === 1) return reply(500, {detail:{message:'Camera unavailable'}});
        if (requests.length === 3) {
            release = () => reply(500, {detail:{message:'Failure from old server'}});
            return;
        }
        return reply(200,{pipeline_id:'pipeline',camera_group_id:'group',resolved_config:body.realtimeConfig});
    });
    await page.goto('https://realtime-control.test/');
    const bundle = await build({stdin:{contents:`
        import React from 'react'; import {createRoot} from 'react-dom/client'; import {Provider} from 'react-redux';
        import {store} from './src/store/store';
        import {RealtimeProcessingButton} from './src/components/control-panels/realtime-panel/RealtimeProcessingButton';
        import {OperationErrorBanner} from './src/components/common/OperationErrorBanner';
        import {useRealtimePipelineSync} from './src/hooks/useRealtimePipelineSync';
        import {pipelineConfigUpdated} from './src/store/slices/realtime/realtime-slice';
        import {serverDisconnected,wsConnectionChanged,serverStateReceived} from './src/store/slices/connection/connection-slice';
        let pid=1;
        window.observe = alive => store.dispatch(serverStateReceived({server_pid:pid,state:{camera_groups:{},
            realtime_pipelines:alive?[{id:'pipeline',camera_group_id:'group',camera_ids:[],alive:true}]:[]}}));
        window.reconnect = () => {store.dispatch(serverDisconnected());pid++;store.dispatch(wsConnectionChanged(true));window.observe(false);};
        window.edit = enabled => {const config=structuredClone(store.getState().realtime.pipelineConfig);
            config.camera_node_config.detector_type='dlc';config.aggregator_config.triangulation_enabled=false;
            config.camera_node_config.skeleton_tracking_enabled=enabled;store.dispatch(pipelineConfigUpdated(config));};
        window.reconnect();window.edit(false);
        function App(){const state=useRealtimePipelineSync();return <><OperationErrorBanner/>
            <RealtimeProcessingButton connected={state.isConnected} loading={state.isLoading} onToggle={state.toggleConnection}/></>}
        createRoot(document.getElementById('root')).render(<Provider store={store}><App/></Provider>);
    `,resolveDir:resolve('.'),loader:'tsx'},bundle:true,write:false,format:'esm',
        alias:{'@':resolve('src')},loader:{'.yaml':'text'},define:{'import.meta.env':'{}'}});
    await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});
    const button = page.getByRole('button',{name:'Real-time processing',exact:true});
    await button.click();
    await expect(page.getByRole('alert')).toContainText('Camera unavailable');
    await expect(page.getByRole('alert')).not.toContainText('[object Object]');
    await expect(button).toHaveText('Real-time processing');
    await expect(button).toBeEnabled();
    await page.evaluate(() => (window as any).edit(true));
    await button.click();
    await expect.poll(() => requests.length).toBe(2);
    expect(requests[1].realtimeConfig.camera_node_config.skeleton_tracking_enabled).toBe(true);
    await expect(button).toHaveAttribute('aria-pressed','true');
    await expect(page.getByRole('alert')).toHaveCount(0);
    await page.evaluate(() => (window as any).observe(false));
    await expect(button).toHaveAttribute('aria-pressed','false');
    await button.click();
    await expect.poll(() => requests.length).toBe(3);
    await expect(button).toBeEnabled();
    await page.evaluate(() => (window as any).reconnect());
    await expect(button).toHaveAttribute('aria-busy','false');
    await release!();
    await page.waitForTimeout(100);
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(button).toBeEnabled();
    await button.click();
    await expect.poll(() => requests.length).toBe(4);
    await expect(button).toHaveAttribute('aria-pressed','true');
    await expect(button).toHaveText('Real-time processing');
});
