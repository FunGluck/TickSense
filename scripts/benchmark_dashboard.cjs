'use strict';
const fs=require('node:fs'), vm=require('node:vm'), {performance}=require('node:perf_hooks');
const html=fs.readFileSync(process.argv[2],'utf8');
const scripts=[...html.matchAll(/<script(?: [^>]*)?>(.*?)<\/script>/gs)].map(x=>x[1]);
const noop=()=>{};
const context=new Proxy({}, {get:()=>noop});
class Element {
  constructor(){this.value='all';this.listeners={};this.style={};this.offsetHeight=180;}
  append(){} replaceChildren(){} setAttribute(){}
  addEventListener(name,fn){const old=this.listeners[name];this.listeners[name]=old?(...args)=>{old(...args);fn(...args);}:fn;}
  getBoundingClientRect(){return {width:1200,height:250,left:0,top:0};}
  getContext(){return context;}
}
const nodes=new Map(), get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
get('report-data').textContent=scripts[0];get('show-stat').checked=true;get('show-events').checked=true;
const scope=vm.createContext({document:{getElementById:get,createElement:()=>new Element()},window:{addEventListener:noop},Intl,Date,console,atob,Blob,Response,DecompressionStream});
const ms=()=>performance.now();
(async()=>{
  const compressed=html.includes('id="report-data" type="application/octet-stream"');
  let start=ms();
  const json=compressed?require('node:zlib').gunzipSync(Buffer.from(scripts[0],'base64')).toString('utf8'):scripts[0];
  JSON.parse(json);const decodeAndParseMs=ms()-start;
  const memory=process.memoryUsage().heapUsed;
  start=ms();
  await vm.runInContext(scripts[1],scope);
  const startupMs=ms()-start;
  if(!get('mspt').width||!get('session').listeners.change)throw Error('Dashboard did not initialize');
  const elapsed=fn=>{const t=ms();fn();return ms()-t;};
  const zoomMs=elapsed(()=>get('mspt').listeners.wheel({preventDefault:noop,clientX:600,deltaY:-20}));
  const markersMs=elapsed(()=>{get('show-ml').checked=true;get('show-ml').listeners.change();});
  const sessionMs=elapsed(()=>{get('session').value='1';get('session').listeners.change();});
  console.log(JSON.stringify({environment:'Node DOM/Canvas doubles',decodeAndParseMs,startupMs,zoomMs,markersMs,sessionMs,
    heapDeltaMiB:(process.memoryUsage().heapUsed-memory)/1048576}));
})().catch(error=>{console.error(error);process.exitCode=1;});
