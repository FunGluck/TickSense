// Logic-only DOM/Canvas doubles. This is not a browser or visual layout test.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.style={};this.value='';this.hidden=false;this.textContent='';this.width=900;this.height=250;this.offsetHeight=180;}
  append(child){this.children.push(child);}
  replaceChildren(){this.children=[];}
  addEventListener(name,fn){this.listeners[name]=fn;}
  getBoundingClientRect(){return {width:900,height:250,left:0,top:0};}
  getContext(){return new Proxy({}, {get:()=>()=>{}});}
}
const nodes={},get=id=>nodes[id]??(nodes[id]=new Element('div'));
const points=[0,1,2,3].map(i=>({timestamp_utc:`2026-11-01T00:00:${String(i*10).padStart(2,'0')}Z`,session_id:i<2?1:2,mspt_avg:i===1?118.33:2,tps_1m:20,csv_row:i+2,source_file:'metrics.csv',ml_anomaly:i===1,stat_anomaly:i===1,anomaly_score:-0.1}));
const episode={signal:'high_mspt',session_id:1,source_file:'metrics.csv',start_utc:points[1].timestamp_utc,last_observed_utc:points[1].timestamp_utc,measurements:1,peak_mspt:118.33,min_tps:20,source_rows:[3],single_observation:true,observed_span_seconds:null,
 explanation:{observed_facts:['Тестовый факт'],possible_interpretation:'Причина не установлена',limitations:['Выборочные данные'],telemetry_context:{gc_time_delta_ms:{available_observations:1,sum_delta:330}}}};
get('report-data').textContent=JSON.stringify({points,events:[episode]});get('session').value='all';
const sandbox={document:{getElementById:get,createElement:t=>new Element(t)},window:{devicePixelRatio:1,innerWidth:1200,innerHeight:900,addEventListener:()=>{}},Intl,Date,console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(__dirname+'/dashboard.js','utf8'),sandbox);
const run=code=>vm.runInContext(code,sandbox);
assert.equal(run('measurements(1)'),'1 измерение');assert.equal(run('measurements(2)'),'2 измерения');assert.equal(run('measurements(5)'),'5 измерений');assert.equal(run('measurements(11)'),'11 измерений');assert.equal(run('measurements(21)'),'21 измерение');
assert.equal(run('num(118.33)'),'118,33');assert.ok(run('date(points[0].timestamp_utc)').endsWith('UTC'));
assert.equal(get('cards').children.length,8);assert.equal(get('event-list').children.length,1);
get('session').value='2';get('session').listeners.change();
assert.equal(run('points.length'),2);assert.equal(run('events.length'),0);assert.equal(get('event-list').children[0].textContent,'Событий не обнаружено');assert.equal(get('ml-list').children[0].textContent,'ML-аномалий не обнаружено');
get('session').value='all';get('session').listeners.change();
get('from').value='250';get('to').value='750';get('from').listeners.input();assert.equal(run('hi-lo'),15000);
get('reset').listeners.click();assert.equal(run('hi-lo'),30000);
get('mspt').listeners.wheel({preventDefault(){},clientX:450,deltaY:-1});assert.equal(run('hi-lo'),22500);
get('mspt').listeners.pointermove({clientX:400,clientY:150});assert.equal(get('tooltip').hidden,false);assert.match(get('tooltip').textContent,/UTC/);
function content(n){return n.textContent+' '+n.children.map(content).join(' ');}
const ui=Object.entries(nodes).filter(([id])=>id!=='report-data').map(([,n])=>content(n)).join(' ');
for(const word of ['high_mspt','gc_time_delta_ms','Measurements','No events','score','undefined'])assert.ok(!ui.includes(word),word);
console.log('Проверены склонения, числа, UTC, фильтр сессий, пустые состояния, масштабирование и подсказки (без браузера).');
