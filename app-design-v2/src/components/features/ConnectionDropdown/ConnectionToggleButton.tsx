/* --- Connection Toggle Button Component --- */
import clsx from "clsx";
import { useAppDispatch, useAppSelector } from "@/store";
import { checkServerHealth } from "@/store/slices/server";

interface ConnectionToggleButtonProps {
    textColor?: string;
}

/* --- Self-contained Toggle Button --- */
export const ConnectionToggleButton = ({
                                                    textColor = "text-gray",
                                                }: ConnectionToggleButtonProps) => {
    const dispatch = useAppDispatch();
    const serverStatus = useAppSelector((state) => state.server.connection.status);

    // Handle button clicks
    const handleClick = () => {
        if (serverStatus === 'disconnected' || serverStatus === 'error') {
            dispatch(checkServerHealth());
        } else if (serverStatus === 'healthy') {
            // TODO: Add proper disconnect action when available
            dispatch(checkServerHealth());
        }
        // Don't do anything if state is 'closing'
    };

    // Get the button configuration based on current state
    const getButtonConfig = () => {
        switch (serverStatus) {
            case 'closing':
                return {
                    text: "Disconnecting...",
                    extraClasses: "loading disabled",
                };
            case 'healthy':
                return {
                    text: "Connected",
                    extraClasses: "activated",
                };
            case 'error':
                return {
                    text: "Error",
                    extraClasses: "error",
                };
            default: // 'disconnected'
                return {
                    text: "Connect",
                    extraClasses: "",
                };
        }
    };

    const { text, extraClasses } = getButtonConfig();

    return (
        <button
            onClick={handleClick}
            disabled={serverStatus === 'closing'}
            className={clsx(
                "gap-1 br-1 button sm flex-inline text-left items-center",
                extraClasses
            )}
        >
            <p className={`${textColor} text md text-align-left`}>{text}</p>
        </button>
    );
};
