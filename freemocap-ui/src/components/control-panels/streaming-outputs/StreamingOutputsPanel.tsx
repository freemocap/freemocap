import React, {useEffect, useRef, useState} from 'react';
import {ApiError, createHttpClient, type OperationData} from '@freemocap/client/http';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import IconButton from '@/components/ui-components/IconButton';
import {useAppSelector} from '@/store/hooks';
import {serverUrls} from '@/constants/server-urls';

type Capability = OperationData<'streaming_list_protocols'>[number];
type Output = OperationData<'streaming_list_outputs'>[number];
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
    const [protocol, setProtocol] = useState('');
    const [config, setConfig] = useState<Record<string, unknown>>({});
    const [pipeline, setPipeline] = useState('');
    const [queueCapacity, setQueueCapacity] = useState(8);
    const [error, setError] = useState('');
    const [commandError, setCommandError] = useState('');
    const [busy, setBusy] = useState(false);
    const [observedOrigin, setObservedOrigin] = useState('');
    const epoch = useRef(0);
    const mounted = useRef(false);
    const requests = useRef(new Set<AbortController>());
    const activeMutation = useRef(false);
    const currentOrigin = useRef('');
    const capability = capabilities.find(item => item.protocol === protocol);
    const schema = (capability?.config_schema ?? {}) as Schema;

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
                setProtocol(''); setConfig({}); setPipeline(''); setError(''); setCommandError('');
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
                        setProtocol(previous => {
                            if (available.data.some(item => item.protocol === previous)) return previous;
                            const first = available.data.find(item => item.available) ?? available.data[0];
                            setConfig(defaults((first?.config_schema ?? {}) as Schema));
                            return first?.protocol ?? '';
                        });
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

    async function mutate(output?: Output, quickVmc = false) {
        const origin = serverUrls.getHttpUrl();
        // Never apply IDs/configuration observed on a different server.
        if (origin !== observedOrigin || activeMutation.current) return;
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
                : quickVmc ? await client.operations.streaming_start_vmc({signal: controller.signal})
                : await client.operations.streaming_create_output({body: {protocol, pipeline_id: pipeline.trim() || null,
                    config, queue_capacity: queueCapacity}, signal: controller.signal});
            if (mounted.current && generation === epoch.current && origin === serverUrls.getHttpUrl()) {
                setOutputs(previous => [...previous.filter(item => item.id !== result.data.id), result.data]);
            }
        } catch (cause) {
            if (mounted.current && generation === epoch.current && origin === serverUrls.getHttpUrl()) {
                setCommandError(`Request failed: ${errorText(cause)}`);
            }
        } finally {
            clearTimeout(timeout); requests.current.delete(controller); activeMutation.current = false;
            if (mounted.current) { setBusy(false); refresh(value => value + 1); }
        }
    }

    function fieldControl(name: string, original: Field) {
        const field = original.anyOf?.find(item => item.type !== 'null') ?? original;
        const value = config[name];
        const update = (next: unknown) => setConfig(previous => ({...previous, [name]: next}));
        const fieldLabel = label(name);
        if (field.type === 'boolean') return <label className="text sm flex flex-col gap-1" key={name}><input className="input-field text sm br-1" aria-label={fieldLabel} type="checkbox"
            checked={value === true} onChange={event => update(event.target.checked)}/>{fieldLabel}</label>;
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
            <ButtonSm text="Start VMC" className="secondary" textColor="text-gray"
                disabled={busy || !observedOrigin || !capabilities.some(item => item.protocol === 'vmc' && item.available)}
                onClick={() => void mutate(undefined, true)}/>
            <ButtonSm text="Refresh" buttonType="secondary" textColor="text-white" disabled={busy}
                onClick={() => refresh(value => value + 1)}/>
            <span className="text sm text-gray">127.0.0.1:39539</span>
        </div>
        {error && <p className="text sm text-red" role="alert">{error}</p>}
        {commandError && <p className="text sm text-red" role="alert">{commandError}</p>}
        <span className="text sm text-gray">{observedAt ? `Status checked ${observedAt}` : 'Status not checked'}</span>
        {outputs.filter(output => output.status !== 'stopped').map(output => <div key={output.id} aria-label={`Output ${output.id}`}
            className="flex flex-row items-center justify-between gap-1">
            <span className="text sm">{output.protocol.toUpperCase()} · <span data-testid="output-state">{output.status}</span>
                {output.error && <span role="alert" className="text-red"> · {output.error}</span>}</span>
            <ButtonSm text={output.protocol === 'vmc' ? 'Stop VMC' : 'Stop output'} buttonType="secondary"
                textColor="text-white" disabled={busy || output.status === 'stopped' || !observedOrigin}
                onClick={() => void mutate(output)}/>
        </div>)}
        <details className="text sm"><summary className="text sm text-gray">Advanced output settings</summary>
            <form onSubmit={event => {event.preventDefault(); void mutate();}} className="flex flex-col gap-1 p-1">
                <label className="text sm">Protocol<select className="input-field text sm br-1" aria-label="Protocol" value={protocol} onChange={event => {
                    setProtocol(event.target.value);
                    setConfig(defaults((capabilities.find(item => item.protocol === event.target.value)?.config_schema ?? {}) as Schema));
                }}>{capabilities.map(item => <option key={item.protocol} value={item.protocol}>{item.protocol.toUpperCase()}</option>)}</select></label>
                {capability?.unavailable_reason && <p className="text sm text-gray" role="status">{capability.unavailable_reason}</p>}
                <label className="text sm">Source pipeline ID<input className="input-field text sm br-1" aria-label="Source pipeline ID" value={pipeline}
                    placeholder="Automatic" onChange={event => setPipeline(event.target.value)}/></label>
                {Object.entries(schema.properties ?? {}).map(([name, field]) => fieldControl(name, field))}
                <label className="text sm">Queue capacity<input className="input-field text sm br-1" aria-label="Queue capacity" type="number" min={1} max={256} required
                    value={queueCapacity} onChange={event => setQueueCapacity(Number(event.target.value))}/></label>
                <ButtonSm text="Start output" buttonType="secondary" textColor="text-white"
                    disabled={busy || !capability?.available || !observedOrigin}/>
            </form>
        </details>
    </section>;
}
