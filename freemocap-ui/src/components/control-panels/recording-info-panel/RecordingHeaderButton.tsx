import React from "react";

interface RecordingHeaderButtonProps {
    isRecording: boolean;
    isPending: boolean;
    disabled: boolean;
    onClick: () => void;
}

export const RecordingHeaderButton: React.FC<RecordingHeaderButtonProps> = ({
    isRecording,
    isPending,
    disabled,
    onClick,
}) => {
    const handleClick = (e: React.MouseEvent): void => {
        e.stopPropagation();
        onClick();
    };

    return (
        <button
            className="button icon-button br-1 p-1"
            onClick={handleClick}
            disabled={disabled || isPending}
            title={isRecording ? "Stop Recording" : "Start Recording"}
            style={{
                color: isRecording ? 'var(--color-danger)' : 'inherit',
                opacity: disabled && !isRecording ? 0.4 : 1,
                transition: "color 0.2s ease",
                animation: isRecording ? 'pulse-record 2s infinite ease-in-out' : undefined,
            }}
        >
            {isPending ? (
                <span className="icon loader-icon icon-size-20" />
            ) : isRecording ? (
                <span className="icon stop-icon icon-size-20" />
            ) : (
                <span className="icon record-icon icon-size-20" />
            )}
        </button>
    );
};
