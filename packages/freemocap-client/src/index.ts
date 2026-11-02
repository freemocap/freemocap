import {createHttpClient, type ClientOptions} from './http.js';
import {TransportService} from './transport/TransportService.js';
export * from './http.js';
export type {paths,components,operations} from './generated/schema.js';
export {operationDefinitions} from './generated/operations.js';
export * from './transport/message-contract.js';
export * from './transport/frame-types.js';
export * from './transport/frame-resolution.js';
export * from './transport/cbor-codec.js';
export * from './transport/TransportService.js';
export * from './transport/application-kinds.js';
export * from './transport/websocket-connection.js';
export * from './transport/log-record.js';
export * from './transport/content-equality.js';
export * from './transport/snapshot-equality.js';

/** Complete HTTP client and an explicit, initially disconnected streaming session. */
export function createClient(options:ClientOptions){
 const http=createHttpClient(options);
 const url=new URL(options.baseUrl.replace(/\/$/,'')+'/websocket/connect');
 url.protocol=url.protocol==='https:'?'wss:':'ws:';
 const stream=new TransportService({url:url.href,socketFactory:options.socketFactory});
 return {...http,stream,close(){stream.disconnect();}};
}
