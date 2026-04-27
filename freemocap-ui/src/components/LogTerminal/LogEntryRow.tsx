import React, {useState} from 'react';
import {LogRecord} from '@/services/server/server-helpers/log-store';
import {LOG_COLORS, LINE_HEIGHT, ROW_PADDING} from './constants';
import {Linkify} from './Linkify';
import {LogEntryDetail} from './LogEntryDetail';

interface Props {
    log: LogRecord;
    style: React.CSSProperties;
}

export const LogEntryRow = React.memo(({log, style}: Props) => {
    const [expanded, setExpanded] = useState(false);
    const color = LOG_COLORS[log.levelname.toUpperCase()] || '#ccc';
    const multiLine = log.message.includes('\n');

    return (
        <div
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
                <span style={{color: '#888', marginRight: 8, fontSize: '0.9em'}}>
                    {log.asctime}
                </span>
                <span
                    style={{
                        backgroundColor: color,
                        color: '#000',
                        padding: '1px 5px',
                        borderRadius: 2,
                        fontSize: '0.75em',
                        fontWeight: 600,
                        marginRight: 8,
                        display: 'inline-block',
                        lineHeight: 'normal',
                        verticalAlign: 'middle',
                    }}
                >
                    {log.levelname}
                </span>
                <span style={{color: '#fff'}}>
                    <Linkify text={multiLine ? log.message.split('\n')[0] : log.message}/>
                </span>
            </div>

            {/* Remaining lines for multi-line messages */}
            {multiLine && (
                <div style={{whiteSpace: 'pre', color: '#fff', paddingLeft: 4}}>
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
