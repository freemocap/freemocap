import { useEffect, useState } from 'react';

export const useWebSocket = (url: string) => {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const [socket, setSocket] = useState<WebSocket | null>(null);

  useEffect(() => {
    let attempt = 0;

    const connect = () => {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
        attempt = 0;
        console.log('WebSocket is connected');
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log(`WebSocket is closed, attempting to reconnect (attempt ${attempt + 1})`);
        setTimeout(() => {
          attempt++;
          connect();
        }, Math.min(1000 * Math.pow(2, attempt), 30000)); // Exponential backoff
      };

      ws.onmessage = (event) => {
        console.log('WebSocket message received with length:', event.data.length);
        setMessages(prevMessages => [...prevMessages, event.data]);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      setSocket(ws);
    };

    connect();

    return () => {
      if (socket) {
        socket.close();
      }
    };
  }, [url]);

  return { isConnected, messages };
};