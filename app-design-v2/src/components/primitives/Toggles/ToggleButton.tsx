
/* --- Connection states (enum-like) --- */
import {STATES} from "@/components/connection-states.tsx";
import clsx from "clsx";



/* --- Reusable Toggle Button --- */
export const ToggleButtonComponent = ({
                                   state,
                                   connectConfig,
                                   connectingConfig,
                                   connectedConfig,
                                   textColor = "text-gray",
                                   onConnect = () => {},
                                   onDisconnect = () => {},
                               }) => {
    // Handle button clicks
    const handleClick = () => {
        if (state === STATES.DISCONNECTED) {
            onConnect(); // trigger connect
        } else if (state === STATES.CONNECTED) {
            onDisconnect(); // trigger disconnect
        }
    };

    // Get the right config based on current state
    const getButtonConfig = () => {
        switch (state) {
            case STATES.CONNECTING:
                return connectingConfig;
            case STATES.CONNECTED:
                return connectedConfig;
            default:
                return connectConfig;
        }
    };

    const { text, iconClass, rightSideIcon, extraClasses } = getButtonConfig();

    return (
        <button
            onClick={handleClick}
            disabled={state === STATES.CONNECTING}
            className={clsx(
                "gap-1 br-1 button sm flex-inline text-left items-center",
                extraClasses
            )}
        >
            {/* Optional left-side icon */}
            {iconClass && <span className={`icon icon-size-16 ${iconClass}`} />}
            <p className={`${textColor} text md text-align-left`}>{text}</p>
            {/* Optional right-side icon */}
            {rightSideIcon && (
                <span className={`icon icon-size-16 ${rightSideIcon}`} />
            )}
        </button>
    );
};
