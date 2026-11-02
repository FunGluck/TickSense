'use strict';
// Presentation-only strings live here to allow another locale later.
const RU = {
  high_mspt:'Высокий MSPT',low_tps:'Низкий TPS',elevated_mspt:'Повышенный MSPT',
  measurements:'Измерения',sessions:'Сессии сервера',mean:'Средний MSPT',peak:'Максимальный MSPT',
  minimum:'Минимальный TPS',ml:'ML-аномалии',stat:'Статистические аномалии',episodes:'Пороговые эпизоды',
  noEvents:'Событий не обнаружено',noML:'ML-аномалий не обнаружено',noData:'Нет данных в выбранном диапазоне',
  unknown:'Данные недоступны',session:'Сессия',rows:'Исходные строки CSV',file:'Файл',
  loaded_chunks_delta:'Изменение числа загруженных чанков',entities_delta:'Изменение числа сущностей',
  gc_count_delta:'Прирост числа сборок GC',gc_time_delta_ms:'Прирост накопленного времени GC',heap_used_ratio:'Доля использованной выделенной памяти JVM',
  facts:'Наблюдаемые факты',interpretation:'Возможная интерпретация',limits:'Ограничения',context:'Числовой контекст',
  single:'Одиночное наблюдение',span:'Наблюдаемый охват',sum:'Сумма доступных интервальных приростов',
  net:'Сумма знаковых изменений',positive:'Максимальный положительный прирост',coverage:'Доступно наблюдений',
  score:'Оценка модели',time:'Время, UTC',start:'Начало',last:'Последнее наблюдение',
  more:'Показать ещё',allML:'Показаны все ML-аномалии'
};
const data=JSON.parse(document.getElementById('report-data').textContent);
const $=id=>document.getElementById(id), num=(n,d=2)=>n===null||n===undefined||!Number.isFinite(Number(n))?'—':new Intl.NumberFormat('ru-RU',{maximumFractionDigits:d}).format(n);
const plural=(n,forms)=>forms[(n%100>=11&&n%100<=14)?2:(n%10===1?0:(n%10>=2&&n%10<=4?1:2))];
const measurements=n=>`${num(n,0)} ${plural(n,['измерение','измерения','измерений'])}`;
const date=t=>t?new Intl.DateTimeFormat('ru-RU',{timeZone:'UTC',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(t))+' UTC':'—';
const text=value=>String(value??'').replace(/(\d)\.(\d)/g,'$1,$2');
function el(tag,content,parent,cls){const n=document.createElement(tag);if(content!==undefined)n.textContent=content;if(cls)n.className=cls;if(parent)parent.append(n);return n;}
const sessions=[...new Set(data.points.map(p=>String(p.session_id)))];
sessions.forEach(s=>{const o=el('option',`${RU.session} ${s}`,$('session'));o.value=s;});
let points=[],events=[],lo=0,hi=1,fullLo=0,fullHi=1,mlLimit=50;
const time=p=>Date.parse(p.timestamp_utc), belongs=x=>$('session').value==='all'||String(x.session_id)===$('session').value;
function refresh(){
  points=data.points.filter(belongs);events=data.events.filter(belongs);mlLimit=50;
  const times=points.map(time).filter(Number.isFinite);fullLo=times.length?Math.min(...times):0;fullHi=times.length?Math.max(...times):1;
  if(fullHi===fullLo){fullLo-=500;fullHi+=500;}lo=fullLo;hi=fullHi;
  $('from').value=0;$('to').value=1000;
  const values=points.map(p=>p.mspt_avg).filter(v=>v!==null&&Number.isFinite(v)),tps=points.map(p=>p.tps_1m).filter(v=>v!==null&&Number.isFinite(v));
  const cards=[[RU.measurements,num(points.length,0)],[RU.sessions,num(new Set(points.map(p=>p.session_id)).size,0)],
    [RU.mean,values.length?num(values.reduce((a,b)=>a+b,0)/values.length)+' мс':'—'],[RU.peak,values.length?num(Math.max(...values))+' мс':'—'],
    [RU.minimum,tps.length?num(Math.min(...tps)):'—'],[RU.ml,num(points.filter(p=>p.ml_anomaly).length,0)],
    [RU.stat,num(points.filter(p=>p.stat_anomaly).length,0)],[RU.episodes,num(events.length,0)]];
  $('cards').replaceChildren();cards.forEach(([label,value])=>{const c=el('div',undefined,$('cards'),'card');el('span',label,c);el('strong',value,c);});
  renderEvents();renderML();drawAll();
}
function list(title,items,parent){el('h4',title,parent);const ul=el('ul',undefined,parent);items.forEach(v=>el('li',text(v),ul));}
function renderEvents(){
  const target=$('event-list');target.replaceChildren();$('event-count').textContent=`Регистраций сигналов: ${num(events.length,0)}`;
  if(!events.length){el('p',RU.noEvents,target,'empty');return;}
  events.forEach(e=>{
    const card=el('details',undefined,target),summary=el('summary',undefined,card);
    el('strong',RU[e.signal]??RU.unknown,summary);el('span',`${date(e.start_utc)} · ${measurements(e.measurements)}`,summary);
    const stats=el('div',undefined,card,'stats');
    [ `${RU.session}: ${e.session_id}`,`${RU.start}: ${date(e.start_utc)}`,`${RU.last}: ${date(e.last_observed_utc)}`,
      `${RU.peak}: ${num(e.peak_mspt)} мс`,`${RU.minimum}: ${num(e.min_tps)}`,
      e.single_observation?RU.single:`${RU.span}: ${num(e.observed_span_seconds)} с`].forEach(v=>el('span',v,stats));
    el('p',`${RU.file}: ${e.source_file??'—'} · ${RU.rows}: ${e.source_rows.map(v=>num(v,0)).join(', ')}`,card,'muted');
    const ex=e.explanation;
    if(!ex){el('p',RU.unknown,card);return;}
    el('h4',RU.context,card);const context=el('div',undefined,card,'context');
    Object.entries(ex.telemetry_context??{}).forEach(([key,v])=>{
      const p=el('p',undefined,context);el('strong',RU[key]??RU.unknown,p);el('br',undefined,p);
      if(!v.available_observations){el('span',RU.unknown,p);return;}
      let description;
      if(key==='heap_used_ratio')description=`Минимум: ${num(v.min*100)} % · Максимум: ${num(v.max*100)} %`;
      else if(key==='gc_count_delta'||key==='gc_time_delta_ms')description=`${RU.sum}: ${num(v.sum_delta)}${key==='gc_time_delta_ms'?' мс':''}`;
      else description=`${RU.net}: ${num(v.net_delta)} · ${RU.positive}: ${num(v.max_positive_delta)}`;
      el('span',description,p);el('br',undefined,p);el('small',`${RU.coverage}: ${num(v.available_observations,0)} из ${num(e.measurements,0)}`,p);
    });
    list(RU.facts,ex.observed_facts??[],card);el('h4',RU.interpretation,card);el('p',text(ex.possible_interpretation),card);list(RU.limits,ex.limitations??[],card);
  });
}
function renderML(){
  const target=$('ml-list');target.replaceChildren();const rows=points.filter(p=>p.ml_anomaly).slice().sort((a,b)=>a.anomaly_score-b.anomaly_score);
  $('more').hidden=rows.length<=mlLimit;
  if(!rows.length){el('p',RU.noML,target,'empty');return;}
  const wrap=el('div',undefined,target,'table-wrap'),table=el('table',undefined,wrap),head=el('tr',undefined,el('thead',undefined,table));
  [RU.time,RU.session,RU.rows,'MSPT, мс','TPS',RU.score].forEach(v=>el('th',v,head));
  const body=el('tbody',undefined,table);
  rows.slice(0,mlLimit).forEach(p=>{const tr=el('tr',undefined,body);[date(p.timestamp_utc),String(p.session_id),num(p.csv_row,0),num(p.mspt_avg),num(p.tps_1m),num(p.anomaly_score,6)].forEach(v=>el('td',v,tr));});
  el('p',`${measurements(Math.min(rows.length,mlLimit))} из ${num(rows.length,0)}`,target,'muted');
}
let plotInfo={};
function draw(id,key){
  const canvas=$(id),rect=canvas.getBoundingClientRect(),w=rect.width,h=rect.height,dpr=window.devicePixelRatio||1;
  canvas.width=w*dpr;canvas.height=h*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);
  const rows=points.filter(p=>time(p)>=lo&&time(p)<=hi),valid=rows.filter(p=>p[key]!==null&&Number.isFinite(p[key]));
  const min=0,max=valid.length?Math.max(key==='tps_1m'?20:1,...valid.map(p=>p[key]))*1.1:1;
  const x=t=>52+(t-lo)/(hi-lo)*(w-70),y=v=>h-36-(v-min)/(max-min)*(h-55);
  c.font='11px system-ui';c.strokeStyle='#283246';c.fillStyle='#9baac0';
  for(let i=0;i<=4;i++){const v=max*i/4;c.beginPath();c.moveTo(52,y(v));c.lineTo(w-18,y(v));c.stroke();c.fillText(num(v,1),5,y(v)+4);}
  for(let i=0;i<3;i++){const t=lo+(hi-lo)*i/2,label=new Date(t).toLocaleTimeString('ru-RU',{timeZone:'UTC'});c.fillText(label,Math.min(w-70,Math.max(52,x(t)-25)),h-10);}
  // A change of session/file, missing value or backward timestamp breaks the path.
  c.strokeStyle='#7faeff';c.lineWidth=1.7;c.beginPath();let previous=null;
  rows.forEach(p=>{if(p[key]===null||!Number.isFinite(p[key])){previous=null;return;}
    if(!previous||p.session_id!==previous.session_id||p.source_file!==previous.source_file||time(p)<time(previous))c.moveTo(x(time(p)),y(p[key]));
    else c.lineTo(x(time(p)),y(p[key]));previous=p;});c.stroke();
  const eventRows=new Set(events.flatMap(e=>e.source_rows.map(r=>`${e.session_id}|${e.source_file}|${r}`)));
  valid.forEach(p=>{const px=x(time(p)),py=y(p[key]);
    c.fillStyle='#7faeff';c.beginPath();c.arc(px,py,1.7,0,Math.PI*2);c.fill();
    if(eventRows.has(`${p.session_id}|${p.source_file}|${p.csv_row}`)){c.strokeStyle='#77e1bb';c.lineWidth=1.6;c.strokeRect(px-5,py-5,10,10);}
    if(p.stat_anomaly){c.fillStyle='#ffbd66';c.beginPath();c.arc(px,py,3.5,0,Math.PI*2);c.fill();}
    if(p.ml_anomaly){c.strokeStyle='#fb83ae';c.lineWidth=2;c.beginPath();c.moveTo(px-4,py-4);c.lineTo(px+4,py+4);c.moveTo(px+4,py-4);c.lineTo(px-4,py+4);c.stroke();}
  });
  if(!valid.length)c.fillText(RU.noData,60,h/2);
  plotInfo[id]={rows:valid,x,y,width:w};
}
function drawAll(){draw('mspt','mspt_avg');draw('tps','tps_1m');$('period').textContent=`${date(lo)} — ${date(hi)}`;$('tooltip').hidden=true;}
function setRange(){let a=Number($('from').value),b=Number($('to').value);if(a>=b){a=Math.min(a,999);b=a+1;$('from').value=a;$('to').value=b;}lo=fullLo+(fullHi-fullLo)*a/1000;hi=fullLo+(fullHi-fullLo)*b/1000;drawAll();}
['mspt','tps'].forEach(id=>{
  const canvas=$(id);
  function inspect(e){const info=plotInfo[id],r=canvas.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;
    const nearest=info.rows.reduce((best,p)=>{const distance=Math.hypot(info.x(time(p))-px,info.y(p[id==='mspt'?'mspt_avg':'tps_1m'])-py);return !best||distance<best.distance?{p,distance}:best;},null);
    if(!nearest){$('tooltip').hidden=true;return;}
    const p=nearest.p,signals=events.filter(v=>v.session_id===p.session_id&&v.source_file===p.source_file&&v.source_rows.includes(p.csv_row)).map(v=>RU[v.signal]);
    $('tooltip').textContent=[date(p.timestamp_utc),`${RU.session}: ${p.session_id} · ${RU.rows}: ${num(p.csv_row,0)}`,`MSPT: ${num(p.mspt_avg)} мс · TPS: ${num(p.tps_1m)}`,p.ml_anomaly?`${RU.ml} · ${RU.score}: ${num(p.anomaly_score,6)}`:null,p.stat_anomaly?RU.stat:null,...signals].filter(Boolean).join('\n');
    $('tooltip').hidden=false;$('tooltip').style.left=Math.max(8,Math.min(e.clientX+16,window.innerWidth-370))+'px';$('tooltip').style.top=Math.max(8,Math.min(e.clientY+16,window.innerHeight-$('tooltip').offsetHeight-8))+'px';
  }
  canvas.addEventListener('pointermove',inspect);canvas.addEventListener('click',inspect);canvas.addEventListener('pointerleave',()=>$('tooltip').hidden=true);
  canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect(),fraction=Math.max(0,Math.min(1,(e.clientX-r.left-52)/(r.width-70))),center=lo+(hi-lo)*fraction,span=Math.max(100,Math.min(fullHi-fullLo,(hi-lo)*(e.deltaY>0?1.3:0.75)));
    lo=Math.max(fullLo,Math.min(fullHi-span,center-span*fraction));hi=lo+span;$('from').value=(lo-fullLo)/(fullHi-fullLo)*1000;$('to').value=(hi-fullLo)/(fullHi-fullLo)*1000;drawAll();},{passive:false});
});
$('session').addEventListener('change',refresh);$('from').addEventListener('input',setRange);$('to').addEventListener('input',setRange);
$('reset').addEventListener('click',()=>{$('from').value=0;$('to').value=1000;setRange();});
$('more').addEventListener('click',()=>{mlLimit+=50;renderML();});
window.addEventListener('resize',drawAll);refresh();
