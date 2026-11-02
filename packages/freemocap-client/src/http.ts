import type {operations as SchemaOperations} from './generated/schema.js';
import {operationDefinitions} from './generated/operations.js';

export interface ApiResult<T> {status:number; headers:Headers; data:T;}
export class ApiError extends Error {
 constructor(public readonly status:number, public readonly body:unknown, public readonly headers:Headers, public readonly url:string) {
  super(`FreeMoCap HTTP ${status} for ${url}`); this.name='ApiError';
 }
}
export interface ClientOptions {baseUrl:string; fetch?:typeof globalThis.fetch; headers?:HeadersInit; socketFactory?:(url:URL)=>WebSocket;}
type Parameters<K extends keyof SchemaOperations> = SchemaOperations[K]['parameters'];
type Path<K extends keyof SchemaOperations> = NonNullable<Parameters<K>['path']>;
type Query<K extends keyof SchemaOperations> = NonNullable<Parameters<K>['query']>;
type Body<K extends keyof SchemaOperations> = [NonNullable<SchemaOperations[K]['requestBody']>] extends [never] ? never :
 NonNullable<SchemaOperations[K]['requestBody']> extends {content:infer C} ? C[keyof C] : never;
type BodyInput<K extends keyof SchemaOperations> = [Body<K>] extends [never] ? {body?:never} :
 {} extends Pick<SchemaOperations[K],'requestBody'> ? {body?:Body<K>} : {body:Body<K>};
type QueryInput<K extends keyof SchemaOperations> = [Query<K>] extends [never] ? {query?:never} :
 {} extends Query<K> ? {query?:Query<K>} : {query:Query<K>};
export type OperationInput<K extends keyof SchemaOperations> =
 ([Path<K>] extends [never] ? {path?:never} : {path:Path<K>}) & QueryInput<K> & BodyInput<K> & {headers?:HeadersInit;signal?:AbortSignal;keepalive?:boolean;cache?:RequestCache};
type Responses<K extends keyof SchemaOperations> = SchemaOperations[K]['responses'];
type Successful<R> = R[{[S in keyof R]: `${S & (string|number)}` extends `2${string}` ? S : never}[keyof R]];
type Content<R> = R extends {content:infer C} ? C[keyof C] : undefined;
export type OperationData<K extends keyof SchemaOperations> = K extends 'recordings_stream_video'|'recordings_browser_video_stream'|'recordings_get_recording_parquet' ? Response : Content<Successful<Responses<K>>>;
export type HttpResponseOperations = {[K in keyof SchemaOperations]: {} extends OperationInput<K> ?
 (input?:OperationInput<K>)=>Promise<Response> : (input:OperationInput<K>)=>Promise<Response>};
export type HttpOperations = {[K in keyof SchemaOperations]: {} extends OperationInput<K> ?
 (input?:OperationInput<K>)=>Promise<ApiResult<OperationData<K>>> : (input:OperationInput<K>)=>Promise<ApiResult<OperationData<K>>>};
interface RuntimeInput {path?:Record<string,string|number>;query?:Record<string,unknown>;body?:unknown;headers?:HeadersInit;signal?:AbortSignal;keepalive?:boolean;cache?:RequestCache;}
export interface ResourceOptions {headers?:HeadersInit;signal?:AbortSignal;keepalive?:boolean;cache?:RequestCache;}
export interface HttpClient {
 operations:HttpOperations;
 responses:HttpResponseOperations;
 assetResponse:(path:string, options?:ResourceOptions)=>Promise<Response>;
 schema:(signal?:AbortSignal)=>Promise<ApiResult<unknown>>;
 asset:(path:string, options?:ResourceOptions)=>Promise<ApiResult<Response>>;
 utilities:{
  playbackViewer:(options?:ResourceOptions)=>Promise<ApiResult<Response>>;
  parquetByPath:(path:string, options?:ResourceOptions)=>Promise<ApiResult<Response>>;
 };
}
export function createHttpClient(options:ClientOptions):HttpClient {
 const base=new URL(options.baseUrl);if(!['http:','https:'].includes(base.protocol))throw new TypeError('HTTP(S) base URL required');
 if(base.search||base.hash)throw new TypeError('Base URL must not include query or fragment');
 const baseUrl=base.href.replace(/\/$/,''); const fetcher=options.fetch??globalThis.fetch.bind(globalThis);
 async function send(method:string,template:string,input:RuntimeInput={}):Promise<Response> {
  const path=template.replace(/\{([^}]+)\}/g,(_,key)=>{
   const value=input.path?.[key];if(value===undefined||value===null)throw new TypeError(`Missing path parameter ${key}`);
   return encodeURIComponent(String(value));
  });
  const url=new URL(baseUrl+path);
  for(const [key,value] of Object.entries(input.query??{})){
   if(value===undefined||value===null)continue;
   for(const part of Array.isArray(value)?value:[value]){
    if(!['string','number','boolean'].includes(typeof part))throw new TypeError(`Unsupported query value for ${key}`);
    url.searchParams.append(key,String(part));
   }
  }
  const headers=new Headers(options.headers);new Headers(input.headers).forEach((value,key)=>headers.set(key,value));
  const body=input.body===undefined?undefined:JSON.stringify(input.body);
  if(body!==undefined&&!headers.has('Content-Type'))headers.set('Content-Type','application/json');
  return fetcher(url,{method,headers,body,signal:input.signal,cache:input.cache,keepalive:input.keepalive});
 }
 async function read(response:Response,asset=false):Promise<ApiResult<unknown>> {
  const url=response.url;
  if(!response.ok){const text=await response.text();let detail:unknown=text;try{detail=JSON.parse(text);}catch{}throw new ApiError(response.status,detail,response.headers,url);}
  let data:unknown;
  if(response.status===204||response.status===205)data=undefined;
  else if(asset)data=response;
  else {const text=await response.text();data=text.length ? (response.headers.get('content-type')?.includes('json') ? JSON.parse(text) : text) : undefined;}
  return {status:response.status,headers:response.headers,data};
 }
 const operations=Object.fromEntries(Object.entries(operationDefinitions).map(([key,definition])=>[key,(input?:RuntimeInput)=>send(definition.method,definition.path,input).then(response=>read(response,definition.asset))])) as unknown as HttpOperations;
 const responses=Object.fromEntries(Object.entries(operationDefinitions).map(([key,definition])=>[key,(input?:RuntimeInput)=>send(definition.method,definition.path,input)])) as unknown as HttpResponseOperations;
 const assetResponse=(path:string,input:ResourceOptions={})=>{
  if(!path.startsWith('/')||path.startsWith('//')||path.includes('\\'))throw new TypeError('Server-relative asset path required');
  return send('GET',path,input);
 };
 const request=async(method:string,path:string,input:RuntimeInput={},asset=false)=>read(await send(method,path,input),asset);
 return {operations,responses,assetResponse,schema:(signal)=>request('GET','/openapi.json',{signal}),utilities:{
  playbackViewer:async(input={})=>request('GET','/freemocap/playback/viewer',input,true) as Promise<ApiResult<Response>>,
  parquetByPath:async(path,input={})=>request('GET','/freemocap/playback/parquet',{...input,query:{path}},true) as Promise<ApiResult<Response>>,
 },asset:async(path,input={})=>{
  // Only explicit server resource paths, never local paths or another origin.
  if(!path.startsWith('/')||path.startsWith('//')||path.includes('\\'))throw new TypeError('Server-relative asset path required');
  const result=await request('GET',path,input,true);return result as ApiResult<Response>;
 }};
}
