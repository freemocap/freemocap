import React from "react";
import IconButton from "@/components/ui-components/IconButton";

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
        <IconButton
            icon={isPending ? "loader-icon" : isRecording ? "stop-icon" : "record-icon"}
            className="icon-size-25 p-1"
            onClick={handleClick}
            disabled={disabled || isPending}
            title={isRecording ? "Stop Recording" : "Start Recording"}
            style={{
                color: isRecording ? 'var(--color-danger)' : 'inherit',
                opacity: disabled && !isRecording ? 0.4 : 1,
                transition: "color 0.2s ease",
                animation: isRecording ? 'pulse-record 2s infinite ease-in-out' : undefined,
            }}
        />
    );
};
