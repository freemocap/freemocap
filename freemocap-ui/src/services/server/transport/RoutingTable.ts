// RoutingTable.ts
//
// Map of message_type → handler, plus binary first-byte demux. Features
// register routes instead of editing one giant handleMessage switch (the
// ServerContextProvider's old pattern). Standard-stream sample bytes (first
// byte 10) demux to the sample handler; everything else falls through to a
// catch-all binary handler (the JPEG image stream, first byte 0/1/2).

import { MessageType } from "./types";
import { isStandardStreamSample } from "./StandardStreamDecoder";

export type JsonMessageHandler = (message: Record<string, any>) => void;
export type BinaryMessageHandler = (buf: ArrayBuffer) => void;

export interface RoutingTable {
  /** Register a handler for a JSON message_type (e.g. "stream_schema"). */
  registerJson(messageType: string, handler: JsonMessageHandler): void;
  registerBinary(firstByte: number, handler: BinaryMessageHandler): void;
  /** Handler for binary frames that match no standard-stream byte tag. */
  registerBinaryFallback(handler: BinaryMessageHandler): void;
  routeJson(message: Record<string, any>): void;
  routeBinary(buf: ArrayBuffer): void;
}

export function createRoutingTable(): RoutingTable {
  const jsonRoutes = new Map<string, JsonMessageHandler>();
  const binaryRoutes = new Map<number, BinaryMessageHandler>();
  let binaryFallback: BinaryMessageHandler | null = null;

  return {
    registerJson(messageType, handler): void {
      jsonRoutes.set(messageType, handler);
    },

    registerBinary(firstByte, handler): void {
      binaryRoutes.set(firstByte, handler);
    },

    registerBinaryFallback(handler): void {
      binaryFallback = handler;
    },

    routeJson(message): void {
      const type = typeof message?.message_type === "string" ? message.message_type : null;
      const handler = type !== null ? jsonRoutes.get(type) : undefined;
      if (handler) {
        handler(message);
      }
      // No match → silently ignored (unknown JSON types are the caller's to log).
    },

    routeBinary(buf): void {
      if (isStandardStreamSample(buf)) {
        const handler = binaryRoutes.get(MessageType.SAMPLE_HEADER);
        if (handler) handler(buf);
        return;
      }
      if (binaryFallback) binaryFallback(buf);
    },
  };
}
