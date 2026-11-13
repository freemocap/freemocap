import React, {useEffect, useRef, useState} from 'react';
import {ApiError, createHttpClient, type OperationData} from '@freemocap/client/http';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import IconButton from '@/components/ui-components/IconButton';
import {useAppSelector} from '@/store/hooks';
import {serverUrls} from '@/constants/server-urls';

type Capability = OperationData<'streaming_list_protocols'>[number];
type Output = OperationData<'streaming_list_outputs'>[number];
export function outputStatusLabel(output: Output): string {
    if (output.status === 'failed') return `${output.protocol.toUpperCase()} stopped`;
    if (output.status === 'stopped') return 'Stopped';
    if (output.readiness === 'preparing') return 'Preparing streams';
    if (output.readiness === 'waiting_for_receiver') return 'Available - waiting for a receiver';
    if (output.readiness === 'sending') return 'Sending to connected receivers';
    return output.status === 'idle' ? 'Waiting for source data' : 'Sending';
}

type Field = {type?: string; title?: string; description?: string; default?: unknown; const?: unknown;
    minimum?: number; maximum?: number; enum?: string[]; items?: Field; anyOf?: Field[]; $ref?: string};
type Schema = {properties?: Record<string, Field>; $defs?: Record<string, Field>};
const errorText = (error: unknown) => error instanceof ApiError
    ? `${error.status}: ${JSON.stringify(error.body)}`
    : String(error);
const label = (name: string) => name.replaceAll('_', ' ').replace(/^./, value => value.toUpperCase());
const defaults = (schema: Schema): Record<string, unknown> => Object.fromEntries(
    Object.entries(schema.properties ?? {}).filter(([, field]) => field.default != null)
        .map(([name, field]) => [name, field.default]));
type Draft = {config: Record<string, unknown>; pipeline: string; queueCapacity: number};
const initialDraft = (schema: Schema): Draft => ({
    config: {...defaults(schema), ...(schema.properties?.include_fingers ? {include_fingers: true} : {})},
    pipeline: '', queueCapacity: 8,
});

/** Null selects the no-body default VMC route; edited settings use generic create. */
export function outputStartBody(protocol: string, schema: Schema, draft: Draft) {
    const config = draft.config;
    const expected = defaults(schema);
    const unchanged = Object.keys(config).length === Object.keys(expected).length
        && Object.entries(expected).every(([key, value]) => JSON.stringify(config[key]) === JSON.stringify(value));
    if (protocol === 'vmc' && schema.properties?.include_fingers?.default === true
        && unchanged && !draft.pipeline.trim() && draft.queueCapacity === 8) return null;
    return {protocol, pipeline_id: draft.pipeline.trim() || null, config, queue_capacity: draft.queueCapacity};
}

/** Refresh on connection/source transitions and commands; never poll on a timer. */
export function StreamingOutputsPanel({onClose}: {onClose?: () => void} = {}) {
    const connected = useAppSelector(state => state.connection.isConnected);
    const serverPid = useAppSelector(state => state.connection.serverPid);
    const sources = useAppSelector(state => state.connection.realtimePipelines.map(item => `${item.id}:${item.alive}`).join('|'));
    const origin = serverUrls.getHttpUrl();
    const [refreshVersion, refresh] = useState(0);
    const [observedAt, setObservedAt] = useState('');
    const capabilityCache = useRef<{key: string; data: Capability[]} | null>(null);
    const [capabilities, setCapabilities] = useState<Capability[]>([]);
    const [outputs, setOutputs] = useState<Output[]>([]);
    const [drafts, setDrafts] = useState<Record<string, Draft>>({});
    const [error, setError] = useState('');
    const [commandError, setCommandError] = useState('');
    const [busy, setBusy] = useState(false);
    const [observedOrigin, setObservedOrigin] = useState('');
    const epoch = useRef(0);
    const mounted = useRef(false);
    const requests = useRef(new Set<AbortController>());
    const activeMutation = useRef(false);
    const currentOrigin = useRef('');

    useEffect(() => {
        mounted.current = true;
        // StrictMode can mount the next effect before this one's aborted fetch settles.
        // Keep each request lifetime local rather than reviving it through a shared ref.
        let disposed = false;

        const load = async () => {
            if (disposed) return;
            const origin = serverUrls.getHttpUrl();
            if (currentOrigin.current !== origin) {
                epoch.current++;
                currentOrigin.current = origin;
                for (const request of requests.current) request.abort();
                setOutputs([]); setCapabilities([]); setObservedOrigin('');
                setDrafts({}); setError(''); setCommandError('');
            }
            const generation = epoch.current;
            const controller = new AbortController();
            requests.current.add(controller);
            const timeout = setTimeout(() => controller.abort(), 5000);
            try {
                if (!activeMutation.current) {
                    const client = createHttpClient({baseUrl: origin});
                    const capabilityKey = `${origin}:${connected}:${serverPid}`;
                    const [available, states] = await Promise.all([
                        capabilityCache.current?.key === capabilityKey
                            ? Promise.resolve({data: capabilityCache.current.data})
                            : client.operations.streaming_list_protocols({signal: controller.signal}),
                        client.operations.streaming_list_outputs({signal: controller.signal}),
                    ]);
                    if (!disposed && generation === epoch.current && origin === serverUrls.getHttpUrl()) {
                        capabilityCache.current = {key: capabilityKey, data: available.data};
                        setObservedAt(new Date().toLocaleTimeString());
                        setCapabilities(available.data); setOutputs(states.data); setObservedOrigin(origin);
                        setError('');
                    }
                }
            } catch (cause) {
                if (!disposed && generation === epoch.current && origin === serverUrls.getHttpUrl()) {
                    setError(`Status unavailable: ${errorText(cause)}. Outputs may still be running.`);
                    setObservedOrigin('');
                }
            } finally {
                clearTimeout(timeout);
                requests.current.delete(controller);

            }
        };
        void load();
        return () => {
            disposed = true;
            mounted.current = false; epoch.current++;
            for (const request of requests.current) request.abort();
        };
    }, [origin, connected, serverPid, sources, refreshVersion]);

    async function mutate(protocol: string, output?: Output) {
        const origin = serverUrls.getHttpUrl();
        // Never apply IDs/configuration observed on a different server.
        if (origin !== observedOrigin || activeMutation.current) return;
        if (!output && outputs.some(item => item.protocol === protocol && ['idle', 'running'].includes(item.status ?? ''))) return;
        const schema = (capabilities.find(item => item.protocol === protocol)?.config_schema ?? {}) as Schema;
        const body = outputStartBody(protocol, schema, drafts[protocol] ?? initialDraft(schema));
        const generation = ++epoch.current;
        for (const request of requests.current) request.abort();
        activeMutation.current = true; setBusy(true); setCommandError('');
        const controller = new AbortController();
        requests.current.add(controller);
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const client = createHttpClient({baseUrl: origin});
            const result = output
                ? await client.operations.streaming_stop_output({path: {output_id: output.id}, signal: controller.signal})
                : body === null ? await client.operations.streaming_start_vmc({signal: controller.signal})
                : await client.operations.streaming_create_output({body, signal: controller.signal});
            if (mounted.current && generation === epoch.current && origin === serverUrls.getHttpUrl()) {
                setOutputs(previous => [...previous.filter(item => item.id !== result.data.id), result.data]);
            }
        } catch (cause) {
            if (mounted.current && generation === epoch.current && origin === serverUrls.getHttpUrl()) {
                setCommandError(`${protocol.toUpperCase()} request failed: ${errorText(cause)}`);
            }
        } finally {
            clearTimeout(timeout); requests.current.delete(controller); activeMutation.current = false;
            if (mounted.current) { setBusy(false); refresh(value => value + 1); }
        }
    }

    function updateDraft(protocol: string, schema: Schema, update: (draft: Draft) => Draft) {
        setDrafts(previous => ({...previous, [protocol]: update(previous[protocol] ?? initialDraft(schema))}));
    }

    function fieldControl(protocol: string, schema: Schema, name: string, original: Field) {
        const field = original.anyOf?.find(item => item.type !== 'null') ?? original;
        const value = (drafts[protocol] ?? initialDraft(schema)).config[name];
        const update = (next: unknown) => updateDraft(protocol, schema, previous => ({...previous, config: {...previous.config, [name]: next}}));
        const fieldLabel = label(name);
        if (field.type === 'boolean') return <label className="streaming-output-toggle text sm" key={name}><span>{fieldLabel}</span>
            <input aria-label={fieldLabel} type="checkbox" checked={value === true} onChange={event => update(event.target.checked)}/></label>;
        if (field.const !== undefined) return <p key={name}>{fieldLabel}: {String(field.const).replaceAll('_', ' ')}</p>;
        if (field.enum) return <label className="text sm flex flex-col gap-1" key={name}>{fieldLabel}<select className="input-field text sm br-1" aria-label={fieldLabel}
            value={String(value ?? field.default ?? '')} onChange={event => update(event.target.value)}>
            {field.enum.map(option => <option key={option} value={option}>{label(option)}</option>)}
        </select></label>;
        if (field.type === 'array') {
            const items = field.items?.$ref ? schema.$defs?.[field.items.$ref.split('/').pop()!] : field.items;
            if (items?.enum) return <label className="text sm flex flex-col gap-1" key={name}>{fieldLabel}<select className="input-field text sm br-1" aria-label={fieldLabel} multiple
                value={Array.isArray(value) ? value as string[] : []}
                onChange={event => update(Array.from(event.target.selectedOptions, option => option.value).length
                    ? Array.from(event.target.selectedOptions, option => option.value) : null)}>
                {items.enum.map(option => <option key={option}>{option}</option>)}
            </select><small>No selection uses all supported channels.</small></label>;
            return <label className="text sm flex flex-col gap-1" key={name}>{fieldLabel}<input className="input-field text sm br-1" aria-label={fieldLabel} value={Array.isArray(value) ? value.join(', ') : ''}
                placeholder="All models" onChange={event => update(event.target.value.trim()
                    ? event.target.value.split(',').map(item => item.trim()).filter(Boolean) : null)}/>
                <small>Separate model IDs with commas; leave blank for all models.</small></label>;
        }
        return <label className="text sm flex flex-col gap-1" key={name}>{fieldLabel}<input className="input-field text sm br-1" aria-label={fieldLabel}
            type={field.type === 'integer' || field.type === 'number' ? 'number' : 'text'}
            min={field.minimum} max={field.maximum} step={field.type === 'integer' ? 1 : undefined}
            required value={String(value ?? '')} onChange={event => update(event.target.type === 'number'
                ? (event.target.value === '' ? '' : Number(event.target.value)) : event.target.value)}/>
            {original.description && <small>{original.description}</small>}</label>;
    }

    return <section aria-label="Streaming outputs" className="flex flex-col gap-1 p-1 text text-white">
        <div className="flex items-center justify-content-space-between">
            <SubactionHeader text="Streaming outputs"/>
            {onClose && <IconButton icon="close-icon" ariaLabel="Close streaming outputs" className="icon-size-25 flex-shrink-0" onClick={onClose}/>}
        </div>
        <div className="flex flex-row items-center gap-1">
            <ButtonSm text="Refresh" buttonType="secondary" textColor="text-white" disabled={busy}
                onClick={() => refresh(value => value + 1)}/>
            <span className="text sm text-gray">{observedAt ? `Status checked ${observedAt}` : 'Status not checked'}</span>
        </div>
        {error && <p className="text sm text-error" role="alert">{error}</p>}
        {commandError && <p className="text sm text-error" role="alert">{commandError}</p>}
        {['vmc', 'lsl'].map(protocol => {
            const title = protocol.toUpperCase();
            const capability = capabilities.find(item => item.protocol === protocol);
            const schema = (capability?.config_schema ?? {}) as Schema;
            const draft = drafts[protocol] ?? initialDraft(schema);
            const states = outputs.filter(output => output.protocol === protocol && output.status !== 'stopped');
            const active = states.some(output => ['idle', 'running'].includes(output.status ?? ''));
            return <section key={protocol} aria-label={`${title} output`} className="streaming-output-section flex flex-col gap-1">
                <SubactionHeader text={title}/>
                <form onSubmit={event => {event.preventDefault(); void mutate(protocol);}} className="flex flex-col gap-1">
                    <div className="flex flex-row items-center gap-1">
                        <ButtonSm text={`Start ${title}`} className="secondary" textColor="text-white"
                            disabled={busy || active || !observedOrigin || !capability?.available}/>
                        {protocol === 'vmc' && <span className="text sm text-gray">{String(draft.config.host ?? '127.0.0.1')}:{String(draft.config.port ?? 39539)}</span>}
                    </div>
                    {capability?.unavailable_reason && <p className="text sm text-gray" role="status">{capability.unavailable_reason}</p>}
                    {protocol === 'lsl' && <p className="text sm text-gray">In LabRecorder: Update, select the FreeMoCap streams, then Start. Refresh status here to check connections. Connected does not confirm recording to disk. Frames before a receiver connects are not buffered.</p>}
                    {states.map(output => <div key={output.id} aria-label={`Output ${output.id}`} className="flex flex-row items-center justify-between gap-1">
                        <span className="text sm"><span data-testid="output-state">{outputStatusLabel(output)}</span>
                            {output.error && <span role="alert" className="text-error"> · {output.error}</span>}</span>
                        <button type="button" className="button-sm-group gap-1 br-1 button items-center sm fit-content flex-inline text-left secondary"
                            disabled={busy || !observedOrigin} onClick={() => void mutate(protocol, output)}>
                            <p className="text-white text-nowrap text bg text-align-left">Stop {title}</p>
                        </button>
                    </div>)}
                    {active && <span className="text sm text-gray">Stop before applying new settings.</span>}
                    <details className="settings-disclosure text sm"><summary className="text sm text-gray">{title} settings</summary>
                        <div className="streaming-output-settings flex flex-col gap-1">
                            <label className="text sm">Source pipeline ID<input className="input-field text sm br-1" aria-label={`${title} source pipeline ID`} value={draft.pipeline}
                                placeholder="Automatic" onChange={event => updateDraft(protocol, schema, previous => ({...previous, pipeline: event.target.value}))}/></label>
                            {Object.entries(schema.properties ?? {}).map(([name, field]) => fieldControl(protocol, schema, name, field))}
                            <label className="text sm">Queue capacity<input className="input-field text sm br-1" aria-label={`${title} queue capacity`} type="number" min={1} max={256} required
                                value={draft.queueCapacity} onChange={event => updateDraft(protocol, schema, previous => ({...previous, queueCapacity: Number(event.target.value)}))}/></label>
                        </div>
                    </details>
                </form>
            </section>;
        })}
    </section>;
}
