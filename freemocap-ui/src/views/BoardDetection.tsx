import React from "react";
import {Box} from "@mui/material";
import {useAsync} from "react-use";

export const BoardDetection = () => {
  const [data, setData] = React.useState<string>("");

  useAsync(async () => {
    // const socket = new WebSocket(`ws://localhost:8080/ws/skeleton_detection`);
    const socket = new WebSocket(`ws://localhost:8080/ws/board_detection`);
    window.onbeforeunload = function() {
      socket.onclose = function () {}; // disable onclose handler first
      socket.close();
    };
    socket.onmessage = async (ev: MessageEvent<Blob>) => {
      const byteData = await ev.data.text();
      setData(byteData)
    }
  }, []);

  if (!data) {
    return null;
  }

  return (
    <Box>
      {data && <img src={`data:image/png;base64,${data}`} alt={"video capture"}/>}
    </Box>
  )
}