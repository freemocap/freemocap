import React, {useEffect, useState} from "react";

function formatDuration(startedAt: string): string {
    const seconds = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    const parts: string[] = [];
    if (hours > 0) parts.push(hours.toString().padStart(2, '0'));
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(secs.toString().padStart(2, '0'));
    return parts.join(':');
}

interface RecordingSummaryProps {
    isRecording: boolean;
    startedAt: string | null;
}

export const RecordingSummary: React.FC<RecordingSummaryProps> = ({
    isRecording,
    startedAt,
}) => {
    const [recordingDuration, setRecordingDuration] = useState<string>("");

    useEffect(() => {
        if (!isRecording || !startedAt) {
            setRecordingDuration("");
            return;
        }
        setRecordingDuration(formatDuration(startedAt));
        const id = setInterval(() => setRecordingDuration(formatDuration(startedAt)), 1000);
        return () => clearInterval(id);
    }, [isRecording, startedAt]);

    if (!isRecording) {
        return (
            <span className="text sm text-gray text-nowrap" style={{fontWeight: 500}}>
                Ready
            </span>
        );
    }

    return (
        <span
            className="tag text sm"
            style={{
                backgroundColor: 'var(--color-danger)',
                color: '#fff',
                animation: 'pulse-record 2s infinite ease-in-out',
            }}
        >
            {recordingDuration || "Recording..."}
        </span>
    );
};
