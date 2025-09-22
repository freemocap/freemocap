/* --- Dropdown wrapper with connection controls --- */
import { useAppSelector, type ServerStatus } from "@/store";

import DropdownButton from "@/components/composites/DropdownButton.tsx";
import {ConnectionToggleButton} from "@/components/features/ConnectionDropdown/ConnectionToggleButton.tsx";

const ConnectionDropdown = () => {
    // Get server status from RTK store
    const serverStatus = useAppSelector((state) => state.server.connection.status);

    /* --- Helper: get the correct status icon for a row --- */
    const getStatusIcon = (status: ServerStatus) => {
        switch (status) {
            case 'healthy':
                return "connected-icon";
            case 'closing':
                return "loader-icon";
            case 'error':
                return "error-icon";
            default: // 'disconnected'
                return "warning-icon";
        }
    };

    /* --- Dropdown button state depends on server status --- */
    const getDropdownButtonState = () => {
        switch (serverStatus) {
            case 'healthy':
                return {text: "Connected", iconClass: "connected-icon"};
            case 'closing':
                return {text: "Disconnecting...", iconClass: "loader-icon"};
            case 'error':
                return {text: "Connection Error", iconClass: "error-icon"};
            default: // 'disconnected'
                return {text: "Not Connected", iconClass: "warning-icon"};
        }
    };

    const dropdownButtonState = getDropdownButtonState();

    return (
        <DropdownButton
            /* --- Dropdown main button (summary of all connections) --- */
            buttonProps={{
                text: dropdownButtonState.text,
                iconClass: dropdownButtonState.iconClass,
                rightSideIcon: "dropdown", // chevron arrow
                textColor: "text-gray",
            }}
            /* --- Dropdown content: list of connections --- */
            dropdownItems={
                <div
                    className="connection-container flex flex-col p-1 gap-1 br-1 bg-darkgray border-1 border-mid-black">
                    {/* Server connection row */}
                    <div
                        className="gap-1 p-1 br-1 flex justify-content-space-between items-center h-25"
                    >
                        {/* Left side: status icon + label */}
                        <div className="text-container overflow-hidden flex items-center gap-1">
                            <span
                                className={`icon icon-size-16 ${getStatusIcon(serverStatus)}`}
                            ></span>
                            <p className="text text-nowrap text-left bg">Server</p>
                        </div>

                        {/* Right side: individual toggle button */}
                        <ConnectionToggleButton />
                    </div>

                    {/* Footer info */}
                    <div className="flex flex-row p-1 gap-1">
                        <p className="text-left text">
                            Having trouble connecting? Learn how to connect...
                        </p>
                    </div>
                </div>
            }
        />
    );
};

export {ConnectionDropdown};
