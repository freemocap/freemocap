import React from "react";
import {Box} from "@mui/material";
import {useAsync} from "react-use";

class FramePayload {
  frame!: [string]
  webcam_id!: string
}

export const BoardDetection = () => {
  const [data, setData] = React.useState<any>();

  useAsync(async () => {
    // const socket = new WebSocket(`ws://localhost:8080/ws/skeleton_detection`);
    const socket = new WebSocket(`ws://localhost:8080/ws/board_detection`);
    window.onbeforeunload = function() {
      socket.onclose = function () {}; // disable onclose handler first
      socket.close();
    };
    socket.onmessage = async (ev: MessageEvent<string>) => {
      const obj: FramePayload = JSON.parse(ev.data);
      console.log(obj)
      const b = new Blob(obj.frame);
      console.log(obj.frame)
      const _text = await b.text();
      setData(prev => {
        return {
          ...prev,
          [obj.webcam_id]: _text
        }
      });
    }
  }, []);

  if (!data) {
    return null;
  }
  const webcam_ids = Object.keys(data);
  return (
    <Box>
      {webcam_ids.map((webcam_id) => {
        return <img src={`data:image/png;base64,${data[webcam_id]}`} alt={"video capture"}/>
      })}
    </Box>
  )
}