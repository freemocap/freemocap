// RoutingTable.ts
//
// Map of message_type → handler, plus the binary first-byte demux. Features
// register routes instead of editing one giant handleMessage switch (the
// ServerContextProvider's old pattern). Every binary frame on the connection
// is a standard-stream sample (first byte 10); the camera images ride the
// sample's IMAGE_JPEG block — there is no second image protocol.

import { MessageType } from "./types";
import { isStandardStreamSample } from "./StandardStreamDecoder";

export type JsonMessageHandler = (message: Record<string, any>) => void;
export type BinaryMessageHandler = (buf: ArrayBuffer) => void;

export interface RoutingTable {
  /** Register a handler for a JSON message_type (e.g. "stream_schema"). */
  registerJson(messageType: string, handler: JsonMessageHandler): void;
  registerBinary(firstByte: number, handler: BinaryMessageHandler): void;
  routeJson(message: Record<string, any>): void;
  routeBinary(buf: ArrayBuffer): void;
}

export function createRoutingTable(): RoutingTable {
  const jsonRoutes = new Map<string, JsonMessageHandler>();
  const binaryRoutes = new Map<number, BinaryMessageHandler>();

  return {
    registerJson(messageType, handler): void {
      jsonRoutes.set(messageType, handler);
    },

    registerBinary(firstByte, handler): void {
      binaryRoutes.set(firstByte, handler);
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
      }
      // A binary frame that is not a sample is not a thing on this connection.
    },
  };
}
