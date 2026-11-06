// Logic-only DOM/Canvas doubles. This is not a browser or visual layout test.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.style={};this.value='';this.hidden=false;this.textContent='';this.width=900;this.height=250;this.offsetHeight=180;}
  append(child){this.children.push(child);}
  replaceChildren(){this.children=[];}
  addEventListener(name,fn){const old=this.listeners[name];this.listeners[name]=old?(...args)=>{old(...args);fn(...args);}:fn;}
  setAttribute(key,value){this[key]=value;}
  setPointerCapture(id){this.captured=id;}
  hasPointerCapture(id){return this.captured===id;}
  releasePointerCapture(id){assert.equal(this.captured,id);this.captured=null;}
  getBoundingClientRect(){return {width:900,height:250,left:0,top:0};}
  getContext(){const self=this;return new Proxy({}, {get:(_,key)=>(...args)=>{self.calls??=[];self.calls.push({key,args});}});}
}
const nodes={},get=id=>nodes[id]??(nodes[id]=new Element('div'));
const points=[0,1,2,3].map(i=>({timestamp_utc:`2026-11-01T00:00:${String(i*10).padStart(2,'0')}Z`,session_id:i<2?1:2,mspt_avg:i===1?118.33:2,tps_1m:20,csv_row:i+2,source_file:'metrics.csv',ml_anomaly:i===1,stat_anomaly:i===1,anomaly_score:-0.1,rolling_threshold:118,excess_mspt:0.33}));
const episode={signal:'high_mspt',session_id:1,source_file:'metrics.csv',start_utc:points[1].timestamp_utc,last_observed_utc:points[1].timestamp_utc,measurements:1,peak_mspt:118.33,min_tps:20,source_rows:[3],single_observation:true,observed_span_seconds:null,
 explanation:{observed_facts:['Тестовый факт'],possible_interpretation:'Причина не установлена',limitations:['Выборочные данные'],telemetry_context:{gc_time_delta_ms:{available_observations:1,sum_delta:330}}}};
get('show-events').checked=true;get('show-stat').checked=true;get('show-ml').checked=false;
get('report-data').textContent=JSON.stringify({points,events:[episode],interpretation:{performance_events:1,ml:{count:1,evaluated:4,percent:25},statistical:{count:1,evaluated:4,percent:25},both:1,unique:1,train_measurements:10,test_measurements:4,coverage:[],coverage_warnings:[],weak_coverage_percent:5,conclusion:'Измерения не доказывают лаги.'}});get('session').value='all';
const sandbox={document:{getElementById:get,createElement:t=>new Element(t)},window:{devicePixelRatio:1,innerWidth:1200,innerHeight:900,addEventListener:()=>{}},Intl,Date,console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(__dirname+'/dashboard.js','utf8'),sandbox);
const run=code=>vm.runInContext(code,sandbox);
assert.equal(run('measurements(1)'),'1 измерение');assert.equal(run('measurements(2)'),'2 измерения');assert.equal(run('measurements(5)'),'5 измерений');assert.equal(run('measurements(11)'),'11 измерений');assert.equal(run('measurements(21)'),'21 измерение');
assert.equal(run('num(118.33)'),'118,33');assert.ok(run('date(points[0].timestamp_utc)').endsWith('UTC'));
assert.equal(get('result-cards').children.length,2);assert.match(get('analysis-conclusion').textContent,/Обнаружены периоды/);assert.ok(get('result-cards').children[1].children[1].textContent.includes('25'));
assert.equal(get('ml-list').children[0].children[0].children[0].children[0].children.length,5);
assert.equal(get('ml-technical').children[0].children[0].children[0].children[0].children.length,5);
assert.equal(get('cards').children.length,5);assert.equal(get('event-list').children.length,1);
get('session').value='2';get('session').listeners.change();
assert.equal(run('points.length'),2);assert.equal(run('events.length'),0);assert.equal(get('event-list').children[0].textContent,'Событий не обнаружено');assert.equal(get('ml-list').children[0].textContent,'Необычных изменений не обнаружено');
get('session').value='all';get('session').listeners.change();
run('changeWindow("left",7500);changeWindow("right",-7500)');assert.equal(run('hi-lo'),15000);
get('reset').listeners.click();assert.equal(run('hi-lo'),30000);
get('mspt').listeners.wheel({preventDefault(){},clientX:450,deltaY:-1});assert.equal(run('hi-lo'),22500);
get('mspt').listeners.pointermove({clientX:400,clientY:150});assert.equal(get('tooltip').hidden,false);assert.match(get('tooltip').textContent,/UTC/);
function content(n){return n.textContent+' '+n.children.map(content).join(' ');}
const ui=Object.entries(nodes).filter(([id])=>id!=='report-data').map(([,n])=>content(n)).join(' ');
for(const word of ['high_mspt','gc_time_delta_ms','Measurements','No events','score','undefined'])assert.ok(!ui.includes(word),word);
get('mspt').listeners.pointermove({clientX:run('plotInfo.mspt.x(time(points[1]))'),clientY:run('plotInfo.mspt.y(points[1].mspt_avg)')});assert.match(get('tooltip').textContent,/Превышение: 0,33 мс/);assert.match(get('tooltip').textContent,/Необычные изменения/);
// Actual Canvas commands verify marker visibility independently on both plots.
function markerCounts(id){const calls=get(id).calls??[];return {cross:calls.filter(c=>c.key==='moveTo'&&c.args[1]!==undefined).length,rect:calls.filter(c=>c.key==='strokeRect').length,arcs:calls.filter(c=>c.key==='arc').length};}
function clearDraw(){get('mspt').calls=[];get('tps').calls=[];run('drawAll()');}
clearDraw();const initial=markerCounts('mspt');
assert.equal(get('show-ml').checked,false);assert.equal(initial.rect,1);
get('show-ml').checked=true;get('show-ml').listeners.change();clearDraw();
for(const id of ['mspt','tps'])assert.equal(markerCounts(id).cross,initial.cross+2);
get('show-stat').checked=false;get('show-stat').listeners.change();clearDraw();assert.equal(markerCounts('mspt').arcs,initial.arcs-1);
get('show-events').checked=false;get('show-events').listeners.change();clearDraw();assert.equal(markerCounts('mspt').rect,0);
assert.equal(run('data.points.filter(p=>p.ml_anomaly).length'),1);
get('session').value='2';get('session').listeners.change();assert.equal(get('show-ml').checked,true);assert.equal(get('show-stat').checked,false);
get('session').value='all';get('session').listeners.change();assert.equal(get('show-ml').checked,true);
get('show-ml').checked=false;get('show-stat').checked=true;get('show-events').checked=true;get('show-ml').listeners.change();
console.log('Проверены склонения, числа, UTC, фильтр сессий, пустые состояния, масштабирование и подсказки (без браузера).');

// Navigator Pointer Events: left/right handles and constant-width movement.
const nav=get('navigator'),pointer=(x,id=1)=>({clientX:x,clientY:40,pointerId:id,button:0,isPrimary:true,preventDefault(){}});
get('reset').listeners.click();
nav.listeners.pointerdown(pointer(run('navX(lo)')));assert.equal(nav.captured,1);
nav.listeners.pointermove(pointer(run('navX(fullLo+6000)')));nav.listeners.pointerup(pointer(0));
assert.equal(run('lo-fullLo'),6000);assert.equal(nav.captured,null);
nav.listeners.pointerdown(pointer(run('navX(hi)')));
nav.listeners.pointermove(pointer(run('navX(fullHi-6000)')));nav.listeners.pointerup(pointer(0));
assert.equal(run('hi-fullLo'),24000);
const width=run('hi-lo');
nav.listeners.pointerdown(pointer(run('navX((lo+hi)/2)')));
nav.listeners.pointermove(pointer(run('navX((lo+hi)/2+3000)')));nav.listeners.pointerup(pointer(0));
assert.equal(run('hi-lo'),width);assert.equal(run('lo-fullLo'),9000);
assert.equal(run('plotInfo.mspt.rows.length'),run('plotInfo.tps.rows.length'));
assert.equal(run('plotInfo.mspt.x(lo)'),run('plotInfo.tps.x(lo)'));
run('changeWindow("pan",999999)');assert.equal(run('hi'),run('fullHi'));assert.equal(run('hi-lo'),width);
run('changeWindow("pan",-999999)');assert.equal(run('lo'),run('fullLo'));assert.equal(run('hi-lo'),width);
run('changeWindow("left",999999)');assert.ok(run('hi>lo'));assert.equal(run('hi-lo'),run('minWindow()'));
run('changeWindow("right",-999999)');assert.ok(run('hi>lo'));
get('reset').listeners.click();assert.equal(run('lo'),run('fullLo'));assert.equal(run('hi'),run('fullHi'));
// Cancellation and secondary pointers never keep a stale drag alive.
nav.listeners.pointerdown(pointer(run('navX(lo)')));nav.listeners.pointermove(pointer(100,2));assert.equal(run('lo'),run('fullLo'));
nav.listeners.pointercancel(pointer(0));assert.equal(run('drag'),null);
nav.listeners.pointerdown(pointer(run('navX(lo)')));nav.listeners.lostpointercapture(pointer(0));assert.equal(run('drag'),null);
// Keyboard alternatives and changing sessions reset the same shared window.
const key=(key,shiftKey=false)=>({key,shiftKey,preventDefault(){}});
get('nav-left').listeners.keydown(key('ArrowRight'));assert.equal(run('lo-fullLo'),300);
get('nav-right').listeners.keydown(key('ArrowLeft'));assert.equal(run('fullHi-hi'),300);
const before=run('hi-lo');get('nav-pan').listeners.keydown(key('ArrowRight'));assert.equal(run('hi-lo'),before);
get('nav-pan').listeners.keydown(key('Home'));assert.equal(run('lo'),run('fullLo'));
get('nav-pan').listeners.keydown(key('End'));assert.equal(run('hi'),run('fullHi'));
get('session').value='2';get('session').listeners.change();assert.equal(run('lo'),run('fullLo'));assert.equal(run('hi'),run('fullHi'));
// Dragging the main chart pans in the opposite direction to the pointer.
run('changeWindow("left",2000);changeWindow("right",-2000)');
const main=get('mspt'),oldLo=run('lo');main.listeners.pointerdown(pointer(450));main.listeners.pointermove(pointer(500));main.listeners.pointerup(pointer(500));assert.ok(run('lo')<oldLo);
// Single observation: padded axis, disabled interaction, no division by zero.
run('data.points.splice(1);data.events.splice(0)');get('session').value='all';get('session').listeners.change();
assert.equal(run('navigationEnabled'),false);assert.equal(get('nav-left').disabled,true);assert.ok(run('hi>lo'));
const singleLo=run('lo');nav.listeners.pointerdown(pointer(24));assert.equal(run('drag'),null);assert.equal(run('lo'),singleLo);
run('data.points.splice(0)');get('session').listeners.change();assert.equal(run('points.length'),0);assert.ok(run('Number.isFinite(lo)&&Number.isFinite(hi)'));assert.equal(get('nav-status').textContent,'Нет данных в выбранном диапазоне');
console.log('Проверены границы, перенос, минимальная ширина, синхронизация, capture/cancel, клавиатура, сессии, одиночный и пустой наборы.');

// Boundary belongs only to its real session, and no line is fabricated without scores.
run("data.points.splice(0,data.points.length,...[0,1,2,3].map(i=>({timestamp_utc:new Date(Date.UTC(2026,10,1,0,0,i*10)).toISOString(),session_id:i<2?1:2,mspt_avg:2,tps_1m:20,ml_anomaly:i>=2,stat_anomaly:false,anomaly_score:i>=2?-.1:null})));data.full_period={ml_boundary:{timestamp_utc:data.points[2].timestamp_utc,session_id:2}}");
get('session').value='all';get('session').listeners.change();get('mspt').calls=[];run('drawAll()');
assert.ok(get('mspt').calls.some(c=>c.key==='fillText'&&c.args[0]==='Начало поиска необычных изменений'));
get('session').value='1';get('session').listeners.change();get('mspt').calls=[];run('drawAll()');
assert.ok(!get('mspt').calls.some(c=>c.key==='fillText'&&c.args[0]==='Начало поиска необычных изменений'));
run('data.full_period.ml_boundary=null');get('session').value='all';get('session').listeners.change();get('mspt').calls=[];run('drawAll()');assert.ok(!get('mspt').calls.some(c=>c.key==='fillText'&&c.args[0]==='Начало поиска необычных изменений'));
// A long gap in one session starts a new line segment; no interpolated bridge.
run("data.points.splice(0,data.points.length,...[0,10,120,130].map(t=>({timestamp_utc:new Date(Date.UTC(2026,10,1)+t*1000).toISOString(),session_id:1,mspt_avg:2,tps_1m:20,ml_anomaly:false,stat_anomaly:false})))");
get('session').value='all';get('session').listeners.change();get('mspt').calls=[];run('drawAll()');
const paths=[];let path=[];for(const call of get('mspt').calls){if(call.key==='beginPath')path=[];else if(call.key==='stroke')paths.push(path);else path.push(call);}
assert.ok(paths.some(path=>path.filter(c=>c.key==='moveTo').length===2&&path.filter(c=>c.key==='lineTo').length===2));
// Large history: preserve every point, keep both tables paginated, no point DOM nodes.
run("data.points.splice(0,data.points.length,...Array.from({length:13586},(_,i)=>({timestamp_utc:new Date(Date.UTC(2026,10,5)+i*10000).toISOString(),session_id:1,mspt_avg:i===100?118:3,tps_1m:20,ml_anomaly:i>=9510,stat_anomaly:i===100,anomaly_score:i>=9510?-.1:null})));data.events.splice(0)");
get('mspt').calls=[];get('tps').calls=[];const started=Date.now();get('session').listeners.change();const refreshMs=Date.now()-started;
assert.equal(run('plotInfo.mspt.rows.length'),13586);assert.equal(run('plotInfo.tps.rows.length'),13586);
assert.equal(get('ml-list').children[0].children[0].children[1].children.length,50);
assert.equal(get('ml-technical').children[0].children[0].children[1].children.length,50);
get('mspt').calls=[];get('tps').calls=[];const toggled=Date.now();get('show-ml').checked=true;get('show-ml').listeners.change();console.log(JSON.stringify({canvasDoubleRows:13586,refreshMs,markerToggleMs:Date.now()-toggled}));

run("data.event_insights={ml_episodes:Array.from({length:12},(_,i)=>({session_id:1,start_utc:data.points[i].timestamp_utc,last_observed_utc:data.points[i].timestamp_utc,measurements:1,single_observation:true,peak_mspt:3,min_tps:20,mean_mspt:3,players_min:1,players_max:1,context:{},observed_facts:[],suggested_checks:[],limitation:'Причина не установлена'}))}");
get('session').listeners.change();assert.equal(get('ml-list').children.length,9);assert.equal(get('more').hidden,false);get('more').listeners.click();assert.equal(get('ml-list').children.length,13);assert.equal(get('more').hidden,true);
get('session').value='2';get('session').listeners.change();assert.equal(get('ml-list').children[0].textContent,'Необычных периодов не обнаружено');
