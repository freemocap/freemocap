import React from 'react';
import {useTranslation} from 'react-i18next';
import {LogRecord} from '@/services/server/server-helpers/log-store';
import {Linkify} from './Linkify';

interface Props {
    log: LogRecord;
    color: string;
}

export const LogEntryDetail: React.FC<Props> = ({log, color}) => {
    const {t} = useTranslation();

    return (
        <div
            style={{
                paddingLeft: 16,
                paddingTop: 6,
                paddingBottom: 6,
                fontSize: '0.8em',
                color: '#888',
                borderTop: '1px solid rgba(255,255,255,0.1)',
                whiteSpace: 'pre-wrap',
                lineHeight: '1.4',
                overflow: 'visible',
            }}
            onClick={(e) => e.stopPropagation()}
        >
            <div>Location: {log.module}:{log.funcName}:Line#{log.lineno}</div>
            <div>{t('fileLabel')}: {log.filename}</div>
            <div>{t('timeDelta')}: {log.delta_t}</div>
            <div>{t('pathLabel')}: <Linkify text={log.pathname}/></div>
            {log.formatted_message && (
                <div>{t('rawMessage')}: <Linkify text={log.formatted_message}/></div>
            )}
            <div>Thread: {log.threadName} (ID: {log.thread})</div>
            <div>Process: {log.processName} (ID: {log.process})</div>
            {(log.exc_info || log.exc_text) && (
                <div>
                    <div>{t('exceptionDetails')}:</div>
                    {log.exc_info && <div><Linkify text={log.exc_info}/></div>}
                    {log.exc_text && <div><Linkify text={log.exc_text}/></div>}
                </div>
            )}
            {log.stack_info && (
                <div>
                    <div>{t('stackTrace')}:</div>
                    <pre
                        style={{
                            whiteSpace: 'pre-wrap',
                            background: '#111',
                            padding: 8,
                            borderRadius: 4,
                            margin: '8px 0',
                        }}
                    >
                        <Linkify text={log.stack_info}/>
                    </pre>
                </div>
            )}
        </div>
    );
};
