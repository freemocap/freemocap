import React, {useRef, useState, useEffect} from 'react';
import {LogRecord} from '@/services/server/server-helpers/log-store';
import {LOG_COLORS, LINE_HEIGHT, ROW_PADDING} from './constants';
import {Linkify} from './Linkify';
import {LogEntryDetail} from './LogEntryDetail';

interface Props {
    log: LogRecord;
    style: React.CSSProperties;
}

export const LogEntryRow = React.memo(({log, style}: Props) => {
    // ── Divider entry: session boundary marker ───────────────────────────
    if (log.type === 'divider') {
        return (
            <div
                style={{
                    ...style,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    paddingLeft: 16,
                    paddingRight: 16,
                }}
            >
                <div
                    style={{
                        flex: 1,
                        height: 1,
                        backgroundColor: 'rgba(255,255,255,0.12)',
                    }}
                />
                <span
                    style={{
                        flexShrink: 0,
                        padding: '0 12px',
                        fontSize: '0.7em',
                        fontFamily: 'monospace',
                        color: 'rgba(255,255,255,0.25)',
                        whiteSpace: 'nowrap',
                    }}
                >
                    {log.message}
                </span>
                <div
                    style={{
                        flex: 1,
                        height: 1,
                        backgroundColor: 'rgba(255,255,255,0.12)',
                    }}
                />
            </div>
        );
    }

    // ── Normal log entry ─────────────────────────────────────────────────
    const [expanded, setExpanded] = useState(false);
    const rowRef = useRef<HTMLDivElement>(null);
    const color = LOG_COLORS[log.levelname.toUpperCase()] || '#ccc';
    const multiLine = log.message.includes('\n');

    useEffect(() => {
        if (!expanded) return;
        const handleClickOutside = (e: MouseEvent) => {
            if (rowRef.current && !rowRef.current.contains(e.target as Node)) {
                setExpanded(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [expanded]);

    return (
        <div
            ref={rowRef}
            style={{
                ...style,
                borderLeft: `2px solid ${color}`,
                paddingLeft: 8,
                paddingTop: ROW_PADDING / 2,
                paddingBottom: ROW_PADDING / 2,
                backgroundColor: expanded ? `${color}1a` : 'rgba(0,0,0,0.2)',
                cursor: 'pointer',
                fontFamily: 'monospace',
                fontSize: '0.85em',
                lineHeight: `${LINE_HEIGHT}px`,
                overflow: expanded ? 'visible' : 'hidden',
                position: 'relative',
            }}
            onClick={() => setExpanded((prev) => !prev)}
        >
            {/* Header line: timestamp + level badge + first (or only) message line */}
            <div style={{whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
                <span style={{color: '#888', marginRight: 8, fontSize: '0.7em'}}>
                    {log.asctime}
                </span>
                <span
                    style={{
                        backgroundColor: color,
                        color: '#000',
                        padding: '1px 5px',
                        borderRadius: 2,
                        fontSize: '0.5em',
                        fontWeight: 600,
                        marginRight: 4,
                        display: 'inline-block',
                        lineHeight: 'normal',
                        verticalAlign: 'middle',
                    }}
                >
                    {log.levelname}
                </span>
                {/*Show UI vs Server tag*/}
                {/*<span*/}
                {/*    style={{*/}
                {/*        backgroundColor: log.source === 'ui' ? '#FF9944' : '#4488aa',*/}
                {/*        color: '#000',*/}
                {/*        padding: '1px 5px',*/}
                {/*        borderRadius: 2,*/}
                {/*        fontSize: '0.75em',*/}
                {/*        fontWeight: 600,*/}
                {/*        marginRight: 8,*/}
                {/*        display: 'inline-block',*/}
                {/*        lineHeight: 'normal',*/}
                {/*        verticalAlign: 'middle',*/}
                {/*    }}*/}
                {/*>*/}
                {/*    {log.source === 'ui' ? 'UI' : 'SERVER'}*/}
                {/*</span>*/}
                <span style={{color: color, fontSize: '0.75em'}}>
                    <Linkify text={multiLine ? log.message.split('\n')[0] : log.message}/>
                </span>
            </div>

            {/* Remaining lines for multi-line messages */}
            {multiLine && (
                <div style={{whiteSpace: 'pre', fontSize: '0.75em', color: color, paddingLeft: 4}}>
                    <Linkify text={log.message.split('\n').slice(1).join('\n')}/>
                </div>
            )}

            {/* Expanded metadata overlay */}
            {expanded && (
                <div
                    style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        right: 0,
                        zIndex: 10,
                        backgroundColor: '#1a1a1a',
                        borderLeft: `2px solid ${color}`,
                        borderBottom: `1px solid ${color}`,
                        boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                        overflow: 'auto',
                        maxHeight: 400,
                    }}
                    onClick={(e) => e.stopPropagation()}
                >
                    <LogEntryDetail log={log} color={color}/>
                </div>
            )}
        </div>
    );
});
LogEntryRow.displayName = 'LogEntryRow';
