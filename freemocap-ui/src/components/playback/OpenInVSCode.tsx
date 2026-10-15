import {useCallback, useEffect, useState} from 'react';
import {useElectronIPC} from '@/services';
import ButtonSm from '@/components/ui-components/ButtonSm';
import AnchoredInfo from '@/components/ui-components/AnchoredInfo';

export default function OpenInVSCode({recordingPath}: {recordingPath: string | null}) {
    const {api} = useElectronIPC();
    const [available, setAvailable] = useState(false);
    const [checking, setChecking] = useState(true);
    const [opening, setOpening] = useState(false);
    const [error, setError] = useState('');
    const check = useCallback(async () => {
        setChecking(true);
        setError('');
        try {
            setAvailable(api ? await api.vscode.available.query() : false);
        } catch {
            setAvailable(false);
            setError('Could not check the VS Code link handler. Try checking again.');
        } finally {
            setChecking(false);
        }
    }, [api]);
    useEffect(() => {void check();}, [check]);

    const open = async () => {
        if (!api || !recordingPath) return;
        setOpening(true);
        setError('');
        try {
            await api.vscode.openFolder.mutate({path: recordingPath});
        } catch {
            setError('Could not contact the desktop app. Restart FreeMoCap and try again.');
        } finally {
            setOpening(false);
        }
    };

    return <div className="flex items-center gap-1">
        <ButtonSm text={opening ? 'Opening…' : 'Open in VS Code'} buttonType="secondary"
            disabled={!recordingPath || !api || checking || !available || opening}
            title={!api ? 'Requires the desktop app' : !recordingPath ? 'Select a recording' : checking ? 'Checking for VS Code…' : !available ? 'VS Code link handler not found — see setup information' : 'Open the recording folder in VS Code'}
            onClick={() => void open()}/>
        <AnchoredInfo title="Open in VS Code" link={{label: 'Download VS Code', url: 'https://code.visualstudio.com/download'}}
            text={<>
                <p>Opens the recording folder alongside FreeMoCap using the desktop VS Code link handler.</p>
                <p>If unavailable, install and launch Visual Studio Code, then check again. If already installed, reinstalling may repair its link handler. Adding code to PATH alone does not register it.</p>
                <p><a href="https://code.visualstudio.com/docs/setup/setup-overview" target="_blank" rel="noreferrer">VS Code setup instructions</a></p>
                <ButtonSm text={checking ? 'Checking…' : 'Check again'} disabled={!api || checking} onClick={() => void check()}/>
                <p role="status">{!api ? 'Requires the FreeMoCap desktop app.' : checking ? 'Checking…' : available ? 'VS Code link handler found.' : 'VS Code link handler not found.'}</p>
            </>}/>
        {error && <span role="alert" className="text-error">{error}</span>}
    </div>;
}
