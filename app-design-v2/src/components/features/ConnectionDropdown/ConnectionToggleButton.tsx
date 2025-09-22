/* --- Connection Toggle Button Component --- */
import clsx from "clsx";
import { useAppDispatch, useAppSelector } from "@/store";
import { checkServerHealth } from "@/store/slices/server";
import { ToggleButtonComponent } from "@/components/features/ConnectionDropdown/ConnectionDropdown";
// import { ConnectionDropdown } from "./ConnectionDropdown";



const StandaloneToggleExample = () => {
  const [state, setState] = useState(STATES.DISCONNECTED);

  return (
    <ToggleButtonComponent
      state={state}
      connectConfig={{
        text: "Stream",
        iconClass: "stream-icon",
        rightSideIcon: "",
        extraClasses: "",
      }}
      connectingConfig={{
        text: "Checking...",
        iconClass: "loader-icon",
        rightSideIcon: "",
        extraClasses: "loading disabled",
      }}
      connectedConfig={{
        text: "Streaming",
        iconClass: "streaming-icon",
        rightSideIcon: "",
        extraClasses: "activated",
      }}
      textColor="text-white"
      onConnect={() => {
        console.log("Checking before streaming…");
        setState(STATES.CONNECTING);

        // Simulate async check before streaming
        setTimeout(() => {
          console.log("Streaming started!");
          setState(STATES.CONNECTED);
        }, 2000);
      }}
      onDisconnect={() => {
        console.log("Stopped streaming!");
        setState(STATES.DISCONNECTED);
      }}
    />
  );
};