import type {CSSProperties} from 'react';

export default function PlaybackStatusPanel({title, detail, recording, failed}: {
    title: string; detail: string; recording: string; failed: boolean;
}): React.ReactElement {
    const accent = failed ? 'var(--color-danger)' : 'var(--color-info)';
    const surface: CSSProperties = {width: 'min(520px, 100%)', padding: 32, borderRadius: 16,
        background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border-secondary)'};
    return <div role={failed ? 'alert' : 'status'} style={{display: 'grid', placeItems: 'center',
        flex: 1, minHeight: 360, padding: 32, background: 'var(--color-bg-primary)', borderRadius: 12}}>
        <section style={surface}>
            <div style={{display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24}}>
                <div style={{display: 'grid', placeItems: 'center', width: 44, height: 44, borderRadius: 12,
                    color: accent, background: failed ? 'var(--color-danger-surface)' : 'var(--color-info-surface)'}}>
                    <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                        <rect x="3" y="4" width="18" height="13" rx="3"/><path d="M8 21h8M12 17v4"/>
                        {failed ? <path d="M12 7v4m0 2v1"/> : <path d="M10 8v5m4-5v5"/>}
                    </svg>
                </div>
                <span style={{fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', color: 'var(--color-text-muted)'}}>RECORDING PLAYBACK</span>
            </div>
            <h2 style={{fontSize: 22, fontWeight: 600, margin: '0 0 12px', color: 'var(--color-text-primary)'}}>{title}</h2>
            <p style={{fontSize: 13, lineHeight: 1.7, margin: '0 0 24px', color: 'var(--color-text-secondary)', overflowWrap: 'anywhere'}}>{detail}</p>
            <div style={{paddingTop: 16, borderTop: '1px solid var(--color-border-muted)', fontSize: 12,
                color: 'var(--color-text-muted)', overflowWrap: 'anywhere'}}>{recording || 'Selected recording'}</div>
        </section>
    </div>;
}
