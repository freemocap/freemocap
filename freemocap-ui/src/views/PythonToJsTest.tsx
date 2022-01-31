import React from "react";
import {Box} from "@mui/material";
import {useAsync} from "react-use";
import axios from "axios";

export const PythonToJsTest = () => {
  const [data, setData] = React.useState<object>({});

  useAsync(async () => {
    const response = await axios.get('http://localhost:8080/camera/detect');
    const port_numbers = response.data.cams_to_use.map(x => x.port_number);
    const sockets: WebSocket[] = port_numbers.map(port => new WebSocket(`ws://localhost:8080/ws/${port}`));
    sockets.forEach((socket, index) => {
      socket.onmessage = async (ev: MessageEvent<Blob>) => {
        const byteData = await ev.data.text();
        setData(prev => {
          return {
            ...prev,
            [index]: byteData
          }
        });
      }
    })
  }, []);
  if (!data) {
    return null;
  }

  const keys = Object.keys(data);
  return (
    <Box>
      {
        keys.map(k => {
          return <img src={`data:image/png;base64,${data[k]}`}/>
        })
      }
    </Box>
  )
}