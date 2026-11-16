'use strict';
// Presentation-only strings live here to allow another locale later.
const RU = {
  high_mspt:'Высокий MSPT',low_tps:'Низкий TPS',elevated_mspt:'Повышенный MSPT',
  measurements:'Измерения',sessions:'Сессии сервера',mean:'Средний MSPT',peak:'Максимальный MSPT',
  minimum:'Минимальный TPS',ml:'Необычные изменения',stat:'Резкие изменения MSPT',episodes:'Пороговые эпизоды',
  noEvents:'Событий не обнаружено',noML:'Необычных изменений не обнаружено',noData:'Нет данных в выбранном диапазоне',
  unknown:'Данные недоступны',session:'Сессия',rows:'Исходные строки CSV',file:'Файл',
  loaded_chunks_delta:'Изменение числа загруженных чанков',entities_delta:'Изменение числа сущностей',
  gc_count_delta:'Прирост числа сборок GC',gc_time_delta_ms:'Прирост накопленного времени GC',heap_used_ratio:'Доля использованной выделенной памяти JVM',
  facts:'Наблюдаемые факты',interpretation:'Возможная интерпретация',limits:'Ограничения',context:'Числовой контекст',
  single:'Одиночное наблюдение',span:'Наблюдаемый охват',sum:'Сумма доступных интервальных приростов',
  net:'Сумма знаковых изменений',positive:'Максимальный положительный прирост',coverage:'Доступно наблюдений',
  score:'Оценка модели',time:'Время, UTC',start:'Начало',last:'Последнее наблюдение',
  more:'Показать ещё',allML:'Показаны все ML-отклонения'
};
function unpackReport(payload){
  if(!payload.columns)return payload;
  const columns=payload.columns, keys=Object.keys(columns);
  payload.points=Array.from({length:columns.timestamp_utc?.length??0},(_,index)=>{
    const point={};
    for(const key of keys)point[key]=columns[key][index];
    return point;
  });
  delete payload.columns;
  return payload;
}
const reportNode=document.getElementById('report-data');
const data=unpackReport(typeof decodedReport==='undefined'?JSON.parse(reportNode.textContent):decodedReport);
reportNode.textContent='';
const $=id=>document.getElementById(id);
const numberFormats=new Map();
function num(n,d=2){
  if(n===null||n===undefined||!Number.isFinite(Number(n)))return '—';
  if(!numberFormats.has(d))numberFormats.set(d,new Intl.NumberFormat('ru-RU',{maximumFractionDigits:d}));
  return numberFormats.get(d).format(n);
}
const plural=(n,forms)=>forms[(n%100>=11&&n%100<=14)?2:(n%10===1?0:(n%10>=2&&n%10<=4?1:2))];
const measurements=n=>`${num(n,0)} ${plural(n,['измерение','измерения','измерений'])}`;
const dateFormat=new Intl.DateTimeFormat('ru-RU',{timeZone:'UTC',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3});
const date=t=>t!=null?dateFormat.format(new Date(t))+' UTC':'—';
const text=value=>String(value??'').replace(/(\d)\.(\d)/g,'$1,$2');
function el(tag,content,parent,cls){const n=document.createElement(tag);if(content!==undefined)n.textContent=content;if(cls)n.className=cls;if(parent)parent.append(n);return n;}
const sessions=[...new Set(data.points.map(p=>String(p.session_id)))];
sessions.forEach(s=>{const o=el('option',`${RU.session} ${s}`,$('session'));o.value=s;});
let points=[],events=[],lo=0,hi=1,fullLo=0,fullHi=1,mlLimit=50,navigationEnabled=false,drag=null;
const CANVAS_FONT='13px Inter, "Segoe UI", Arial, sans-serif';
const time=p=>p._time??(p._time=Date.parse(p.timestamp_utc)), belongs=x=>$('session').value==='all'||String(x.session_id)===$('session').value;
let sessionPoints=null,indexedLength=-1,navCache=null,eventIndex=new Map(),rawML=[];
let orderedEvents=[],eventPage=0,mlPage=0,rawPage=0;
function pointsBySession(){
  if(indexedLength===data.points.length)return sessionPoints;
  indexedLength=data.points.length;
  sessionPoints=new Map();
  for(const point of data.points){
    const session=String(point.session_id);
    if(!sessionPoints.has(session))sessionPoints.set(session,[]);
    sessionPoints.get(session).push(point);
  }
  return sessionPoints;
}
const eventKey=(session,source,row)=>`${session}|${source??''}|${row}`;
function refresh(){
  finishDrag();
  const bySession=pointsBySession();
  points=$('session').value==='all'?data.points:bySession.get($('session').value)??[];
  events=data.events.filter(belongs);mlLimit=50;
  eventPage=mlPage=rawPage=0;orderedEvents=prioritizePerformanceEvents(events);
  navCache=null;seriesCache.clear();
  eventIndex=new Map();
  for(const event of events)for(const row of event.source_rows){
    const key=eventKey(event.session_id,event.source_file,row);
    if(!eventIndex.has(key))eventIndex.set(key,[]);
    eventIndex.get(key).push(RU[event.signal]);
  }
  rawML=points.filter(p=>p.ml_anomaly).sort((a,b)=>a.anomaly_score-b.anomaly_score);
  fullLo=points.length?time(points[0]):0;
  fullHi=points.length?time(points.at(-1)):1;
  navigationEnabled=points.length>1&&fullHi>fullLo;
  if(fullHi===fullLo){fullLo-=500;fullHi+=500;}lo=fullLo;hi=fullHi;
  let sum=0,count=0,peak=-Infinity,lowest=Infinity;
  for(const point of points){
    if(Number.isFinite(point.mspt_avg)){sum+=point.mspt_avg;count++;peak=Math.max(peak,point.mspt_avg);}
    if(Number.isFinite(point.tps_1m))lowest=Math.min(lowest,point.tps_1m);
  }
  const sessionCount=$('session').value==='all'?bySession.size:Number(points.length>0);
  const cards=[[RU.measurements,num(points.length,0)],[RU.sessions,num(sessionCount,0)],[RU.minimum,num(lowest)],
    [RU.mean,count?num(sum/count)+' мс':'—'],[RU.peak,count?num(peak)+' мс':'—']];
  $('analysis-conclusion').textContent=!points.length?RU.noData:events.length?
    `Обнаружены периоды повышенного MSPT или снижения TPS: ${num(events.length,0)}. Это повод изучить графики, а не установленная причина лагов.`:
    'Просадок по заданным условиям MSPT/TPS не обнаружено. Необычные изменения сами по себе не означают лаги.';
  $('cards').replaceChildren();cards.forEach(([label,value])=>{const c=el('div',undefined,$('cards'),'card');el('span',label,c);el('strong',value,c);});
  renderEvents();renderML();drawAll();
}
function list(title,items,parent){el('h4',title,parent);const ul=el('ul',undefined,parent);items.forEach(v=>el('li',text(v),ul));}
// Presentation order only. A high-MSPT episode accompanies the first overlapping
// low-TPS episode in the same file/session; each original episode appears once.
function prioritizePerformanceEvents(items){
  const chronological=(a,b)=>Date.parse(a.start_utc)-Date.parse(b.start_utc);
  const low=items.filter(e=>e.signal==='low_tps').sort(chronological);
  const high=items.filter(e=>e.signal==='high_mspt').sort(chronological);
  const elevated=items.filter(e=>e.signal==='elevated_mspt').sort(chronological);
  const used=new Set(),ordered=[];
  for(const episode of low){
    ordered.push(episode);
    for(const companion of high){
      if(!used.has(companion)&&String(companion.session_id)===String(episode.session_id)
         &&(companion.source_file??null)===(episode.source_file??null)
         &&Date.parse(companion.start_utc)<=Date.parse(episode.last_observed_utc)
         &&Date.parse(episode.start_utc)<=Date.parse(companion.last_observed_utc)){
        ordered.push(companion);used.add(companion);
      }
    }
  }
  return [...ordered,...high.filter(e=>!used.has(e)),
    ...items.filter(e=>!['low_tps','high_mspt','elevated_mspt'].includes(e.signal)).sort(chronological),...elevated];
}
function renderEvents(){
  const target=$('event-list');target.replaceChildren();$('event-technical').replaceChildren();$('event-count').textContent=events.length?'Сигналы могут пересекаться':'';
  $('event-prev').hidden=true;$('event-next').hidden=true;
  if(!events.length){el('p',RU.noEvents,target,'empty');return;}
  $('event-prev').hidden=eventPage===0;
  $('event-next').hidden=(eventPage+1)*25>=orderedEvents.length;
  orderedEvents.slice(eventPage*25,(eventPage+1)*25).forEach(e=>{
    const card=el('details',undefined,target),summary=el('summary',undefined,card);
    el('strong',RU[e.signal]??RU.unknown,summary);el('span',`${date(e.start_utc)} · ${measurements(e.measurements)}`,summary);
    const stats=el('div',undefined,card,'stats');
    [ `${RU.session}: ${e.session_id}`,`${RU.start}: ${date(e.start_utc)}`,`${RU.last}: ${date(e.last_observed_utc)}`,
      `${RU.peak}: ${num(e.peak_mspt)} мс`,`${RU.minimum}: ${num(e.min_tps)}`,
      e.single_observation?RU.single:`${RU.span}: ${num(e.observed_span_seconds)} с`].forEach(v=>el('span',v,stats));
    el('p',`${RU[e.signal]??RU.unknown} · ${date(e.start_utc)} · ${RU.session}: ${e.session_id} · ${RU.file}: ${e.source_file??'—'} · ${RU.rows}: ${e.source_rows.map(v=>num(v,0)).join(', ')}`,$('event-technical'),'muted');
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
function renderRawML(showPreview=true){
  const target=$('ml-list'),technical=$('ml-technical');
  if(showPreview)target.replaceChildren();
  technical.replaceChildren();
  const rows=rawML;
  $('more').hidden=rows.length<=mlLimit;
  if(!rows.length){if(showPreview)el('p',RU.noML,target,'empty');return;}
  function table(parent,headers){const wrap=el('div',undefined,parent,'table-wrap'),t=el('table',undefined,wrap),head=el('tr',undefined,el('thead',undefined,t));headers.forEach(v=>el('th',v,head));return el('tbody',undefined,t);}
  if(showPreview){
  const body=table(target,[RU.time,'MSPT, мс','TPS','Игроки','Наблюдение']);
  rows.slice(0,mlLimit).forEach(p=>{const tr=el('tr',undefined,body);const description=p.players_online===0?'Необычное состояние сервера без игроков':'Необычное состояние сервера';
    [date(p.timestamp_utc),num(p.mspt_avg,3),num(p.tps_1m),num(p.players_online,0),description].forEach(v=>el('td',v,tr));});
  }
  const details=table(technical,[RU.time,RU.session,RU.file,RU.rows,RU.score]);
  rows.slice(rawPage*50,(rawPage+1)*50).forEach(p=>{const tr=el('tr',undefined,details);[date(p.timestamp_utc),String(p.session_id),p.source_file??'—',num(p.csv_row,0),num(p.anomaly_score,6)].forEach(v=>el('td',v,tr));});
  if(showPreview)el('p',`${measurements(Math.min(rows.length,mlLimit))} из ${num(rows.length,0)}`,target,'muted');
}
let plotInfo={};
const seriesCache=new Map();
function lowerBound(rows,target,upper=false){
  let start=0,end=rows.length;
  while(start<end){
    const mid=Math.floor((start+end)/2);
    if(time(rows[mid])<target||upper&&time(rows[mid])===target)start=mid+1;
    else end=mid;
  }
  return start;
}
function sampleSeries(rows, start, end, key, from, to, width, markers=false){
  const dense=end-start>width*2, output=[], groups=[[],[],[]];
  const markerBins=markers&&dense?new Map():null;
  const gap=(data.data_quality?.max_gap_seconds??30)*1000;
  let previous=null,bucket=null,max=-Infinity;
  const pixel=t=>Math.max(0,Math.min(width-1,Math.floor((t-from)/(to-from)*width)));
  function flush(){
    if(!bucket)return;
    const indices=[...new Set([bucket.first,bucket.min,bucket.max,bucket.last])].sort((a,b)=>a-b);
    indices.forEach((index,i)=>output.push({point:rows[index],break:bucket.break&&i===0}));
    bucket=null;
  }
  function mark(type,point,column){
    if(!dense){groups[type].push(point);return;}
    const bin=type*width+column,old=markerBins.get(bin);
    if(!old||(key==='mspt_avg'?point[key]>old[key]:point[key]<old[key]))markerBins.set(bin,point);
  }
  for(let i=start;i<end;i++){
    const point=rows[i],value=point[key];
    if(!Number.isFinite(value)){flush();previous=null;continue;}
    const timestamp=time(point);
    const broken=!previous||point.session_id!==previous.session_id||point.source_file!==previous.source_file
      ||timestamp-time(previous)>gap||timestamp<time(previous);
    const column=dense?pixel(timestamp):0;
    max=Math.max(max,value);
    if(!dense)output.push({point,break:broken});
    else{
      if(broken||bucket?.column!==column){
        flush();
        bucket={first:i,last:i,min:i,max:i,column,break:broken};
      }else{
        if(value<rows[bucket.min][key])bucket.min=i;
        if(value>rows[bucket.max][key])bucket.max=i;
        bucket.last=i;
      }
    }
    if(markers){
      if(point.stat_anomaly)mark(1,point,column);
      if(point.ml_anomaly)mark(2,point,column);
      if(eventIndex.size&&eventIndex.has(eventKey(point.session_id,point.source_file,point.csv_row)))mark(0,point,column);
    }
    previous=point;
  }
  flush();
  if(markerBins)for(const [bin,point] of markerBins)groups[Math.floor(bin/width)].push(point);
  return {output,groups,max,dense};
}

function draw(id,key){
  const canvas=$(id),rect=canvas.getBoundingClientRect(),w=rect.width,h=rect.height,dpr=window.devicePixelRatio||1;
  canvas.width=w*dpr;canvas.height=h*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);
  const start=lowerBound(points,lo),end=lowerBound(points,hi,true);
  const cache=seriesCache.get(key);
  let series=cache?.series;
  if(!cache||cache.lo!==lo||cache.hi!==hi||cache.width!==w){
    series=sampleSeries(points,start,end,key,lo,hi,Math.max(1,Math.floor(w-70)),true);
    seriesCache.set(key,{lo,hi,width:w,series});
  }
  const max=Math.max(key==='tps_1m'?20:1,series.max)*1.1;
  const x=t=>52+(t-lo)/(hi-lo)*(w-70),y=v=>h-36-v/max*(h-55);
  c.font=CANVAS_FONT;c.strokeStyle='#283246';c.fillStyle='#9baac0';
  for(let i=0;i<=4;i++){const v=max*i/4;c.beginPath();c.moveTo(52,y(v));c.lineTo(w-18,y(v));c.stroke();c.fillText(num(v,1),5,y(v)+4);}
  for(let i=0;i<3;i++){const t=lo+(hi-lo)*i/2,label=new Date(t).toLocaleTimeString('ru-RU',{timeZone:'UTC'});c.fillText(label,Math.min(w-70,Math.max(52,x(t)-25)),h-10);}
  c.strokeStyle='#7faeff';c.lineWidth=1.7;c.beginPath();
  for(const entry of series.output){
    const p=entry.point;
    c[entry.break?'moveTo':'lineTo'](x(time(p)),y(p[key]));
  }
  c.stroke();
  c.fillStyle='#7faeff';c.beginPath();
  for(const {point:p} of series.output){
    const px=x(time(p)),py=y(p[key]);c.moveTo(px+1.7,py);c.arc(px,py,1.7,0,Math.PI*2);
  }
  c.fill();
  if($('show-events').checked){c.strokeStyle='#77e1bb';c.lineWidth=1.6;
    for(const p of series.groups[0])c.strokeRect(x(time(p))-5,y(p[key])-5,10,10);
  }
  if($('show-stat').checked){c.fillStyle='#ffbd66';c.beginPath();
    for(const p of series.groups[1]){
      const px=x(time(p)),py=y(p[key]);c.moveTo(px+3.5,py);c.arc(px,py,3.5,0,Math.PI*2);
    }
    c.fill();
  }
  if($('show-ml').checked){c.strokeStyle='#fb83ae';c.lineWidth=2;c.beginPath();
    for(const p of series.groups[2]){
      const px=x(time(p)),py=y(p[key]);c.moveTo(px-4,py-4);c.lineTo(px+4,py+4);c.moveTo(px+4,py-4);c.lineTo(px-4,py+4);
    }
    c.stroke();
  }
  if(!series.output.length)c.fillText(RU.noData,60,h/2);
  const boundary=data.full_period?.ml_boundary;
  if(boundary&&($('session').value==='all'||String(boundary.session_id)===$('session').value)){
    const t=Date.parse(boundary.timestamp_utc);
    if(t>=lo&&t<=hi){c.strokeStyle='#9baac0';c.lineWidth=1;c.setLineDash([4,4]);c.beginPath();c.moveTo(x(t),12);c.lineTo(x(t),h-36);c.stroke();c.setLineDash([]);c.fillStyle='#9baac0';c.fillText('Начало поиска необычных изменений',Math.max(52,Math.min(x(t)+6,w-330)),18);}
  }
  plotInfo[id]={start,end,rendered:series.output.length,x,y,width:w,key};
}
function drawAll(){draw('mspt','mspt_avg');draw('tps','tps_1m');drawNavigator();$('period').textContent=points.length?`${date(lo)} — ${date(hi)}`:RU.noData;$('tooltip').hidden=true;}
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
// Keep the handles distinguishable even on a narrow navigator (at least 24 CSS px).
const minWindow=()=>Math.min(fullHi-fullLo,Math.max(1,Math.ceil((fullHi-fullLo)*24/navigatorGeometry().width)));
// All input methods share these bounds and the same lo/hi for both plots.
let redrawPending=false;
function scheduleDraw(){
  if(!window.requestAnimationFrame){drawAll();return;}
  if(redrawPending)return;
  redrawPending=true;
  window.requestAnimationFrame(()=>{redrawPending=false;drawAll();});
}
function changeWindow(mode,delta,startLo=lo,startHi=hi){
  if(!navigationEnabled)return;
  if(mode==='left'){hi=startHi;lo=clamp(startLo+delta,fullLo,hi-minWindow());}
  else if(mode==='right'){lo=startLo;hi=clamp(startHi+delta,lo+minWindow(),fullHi);}
  else{const span=startHi-startLo;lo=clamp(startLo+delta,fullLo,fullHi-span);hi=lo+span;}
  scheduleDraw();
}
function resetWindow(){finishDrag();lo=fullLo;hi=fullHi;drawAll();}
function navigatorGeometry(){const w=$('navigator').getBoundingClientRect().width;return {left:24,width:Math.max(1,w-48)};}
function navX(t){const g=navigatorGeometry();return g.left+(t-fullLo)/(fullHi-fullLo)*g.width;}
function navMode(x){const left=navX(lo),right=navX(hi),hit=14;
  if(Math.min(Math.abs(x-left),Math.abs(x-right))<=hit)return Math.abs(x-left)<=Math.abs(x-right)?'left':'right';
  return x>left&&x<right?'pan':null;
}
function drawNavigator(){
  const canvas=$('navigator'),r=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
  canvas.width=r.width*dpr;canvas.height=r.height*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);c.font=CANVAS_FONT;
  const bottom=r.height-24,g=navigatorGeometry();
  if(!navCache||navCache.width!==g.width){
    navCache={width:g.width,series:sampleSeries(points,0,points.length,'mspt_avg',fullLo,fullHi,Math.max(1,Math.floor(g.width)))};
  }
  const y=v=>bottom-v/Math.max(navCache.series.max,1)*(bottom-12);
  const x=t=>g.left+(t-fullLo)/(fullHi-fullLo)*g.width;
  c.strokeStyle='#7faeff';c.lineWidth=1.5;c.beginPath();
  for(const entry of navCache.series.output){
    const p=entry.point;c[entry.break?'moveTo':'lineTo'](x(time(p)),y(p.mspt_avg));
  }
  c.stroke();
  const left=x(lo),right=x(hi);
  c.fillStyle='#050a13b3';c.fillRect(g.left,0,Math.max(0,left-g.left),bottom);c.fillRect(right,0,Math.max(0,g.left+g.width-right),bottom);
  c.fillStyle='#77e1bb20';c.fillRect(left,0,right-left,bottom);c.strokeStyle='#77e1bb';c.strokeRect(left,1,right-left,bottom-2);
  for(const x of [left,right]){c.fillStyle='#77e1bb';c.fillRect(x-5,bottom/2-18,10,36);c.fillStyle='#10251f';c.fillRect(x-1,bottom/2-7,2,14);}
  const axisTime=t=>new Date(t).toLocaleTimeString('ru-RU',{timeZone:'UTC'})+' UTC';
  c.fillStyle='#9baac0';c.textAlign='left';c.fillText(points.length?axisTime(fullLo):RU.noData,g.left,r.height-4);
  if(navigationEnabled){c.textAlign='right';c.fillText(axisTime(fullHi),g.left+g.width,r.height-4);}
  for(const id of ['nav-left','nav-pan','nav-right'])$(id).disabled=!navigationEnabled;
  $('reset').disabled=!navigationEnabled;
  $('nav-status').textContent=navigationEnabled?`Выбрано: ${date(lo)} — ${date(hi)}`:points.length?'Одно время наблюдения: изменение диапазона недоступно. Отступы оси не означают длительность события.':RU.noData;
  $('nav-left').setAttribute('aria-label',`Начало диапазона: ${date(lo)}. Изменить стрелками.`);
  $('nav-right').setAttribute('aria-label',`Конец диапазона: ${date(hi)}. Изменить стрелками.`);
}
function finishDrag(){if(!drag)return;const old=drag;drag=null;old.canvas.style.cursor='';if(old.canvas.hasPointerCapture(old.id))old.canvas.releasePointerCapture(old.id);}
function bindDrag(canvas,isNavigator){
  canvas.addEventListener('pointerdown',e=>{
    if(!navigationEnabled||drag||e.isPrimary===false||(e.button!==undefined&&e.button!==0))return;
    const r=canvas.getBoundingClientRect(),mode=isNavigator?navMode(e.clientX-r.left):'pan';if(!mode)return;
    e.preventDefault();canvas.setPointerCapture(e.pointerId);
    drag={canvas,id:e.pointerId,mode,x:e.clientX,startLo:lo,startHi:hi,
      timePerPixel:isNavigator?(fullHi-fullLo)/navigatorGeometry().width:(hi-lo)/Math.max(1,r.width-70),isNavigator};
    canvas.style.cursor=mode==='pan'?'grabbing':'ew-resize';$('tooltip').hidden=true;
  });
  canvas.addEventListener('pointermove',e=>{
    if(drag&&drag.canvas===canvas&&drag.id===e.pointerId){e.preventDefault();const delta=(e.clientX-drag.x)*drag.timePerPixel*(isNavigator?1:-1);changeWindow(drag.mode,delta,drag.startLo,drag.startHi);}
    else if(!drag&&isNavigator){const mode=navMode(e.clientX-canvas.getBoundingClientRect().left);canvas.style.cursor=!navigationEnabled?'default':mode==='pan'?'grab':mode?'ew-resize':'default';}
  });
  for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,e=>{if(drag&&drag.canvas===canvas&&drag.id===e.pointerId)finishDrag();});
}
bindDrag($('navigator'),true);
for(const [id,mode] of [['nav-left','left'],['nav-pan','pan'],['nav-right','right']])$(id).addEventListener('keydown',e=>{
  if(!navigationEnabled||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();
  let delta=(fullHi-fullLo)/100*(e.shiftKey?10:1)*(e.key==='ArrowLeft'?-1:1);
  if(e.key==='Home')delta=fullLo-(mode==='right'?hi:lo);
  if(e.key==='End')delta=fullHi-(mode==='right'?hi:mode==='left'?lo:hi);
  changeWindow(mode,delta);
});
['mspt','tps'].forEach(id=>{
  const canvas=$(id);
  function inspect(e){const info=plotInfo[id],r=canvas.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;
    if(drag)return;
    const target=lo+(px-52)/Math.max(1,info.width-70)*(hi-lo);
    const center=clamp(lowerBound(points,target),info.start,info.end);
    let left=center-1,right=center,best=null,distance=Infinity;
    while(left>=info.start||right<info.end){
      const dxLeft=left>=info.start?Math.abs(info.x(time(points[left]))-px):Infinity;
      const dxRight=right<info.end?Math.abs(info.x(time(points[right]))-px):Infinity;
      if(Math.min(dxLeft,dxRight)>distance)break;
      const p=dxLeft<=dxRight?points[left--]:points[right++];
      if(!Number.isFinite(p[info.key]))continue;
      const candidate=Math.hypot(info.x(time(p))-px,info.y(p[info.key])-py);
      if(candidate<distance){best=p;distance=candidate;}
    }
    if(!best){$('tooltip').hidden=true;return;}
    const p=best,signals=eventIndex.get(eventKey(p.session_id,p.source_file,p.csv_row))??[];
    $('tooltip').textContent=[date(p.timestamp_utc),`${RU.session}: ${p.session_id} · Игроки: ${num(p.players_online,0)}`,`MSPT: ${num(p.mspt_avg,3)} мс · TPS: ${num(p.tps_1m)}`,p.ml_anomaly?RU.ml:null,p.stat_anomaly?`${RU.stat} · Локальный порог: ${num(p.rolling_threshold,3)} мс · Превышение: ${num(p.excess_mspt,3)} мс`:null,...signals].filter(Boolean).join('\n');
    $('tooltip').hidden=false;$('tooltip').style.left=Math.max(8,Math.min(e.clientX+16,window.innerWidth-370))+'px';$('tooltip').style.top=Math.max(8,Math.min(e.clientY+16,window.innerHeight-$('tooltip').offsetHeight-8))+'px';
  }
  canvas.addEventListener('pointermove',inspect);canvas.addEventListener('click',inspect);canvas.addEventListener('pointerleave',()=>$('tooltip').hidden=true);
  bindDrag(canvas,false);
  canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect(),fraction=Math.max(0,Math.min(1,(e.clientX-r.left-52)/(r.width-70))),center=lo+(hi-lo)*fraction,span=(hi-lo)*(e.deltaY>0?1.3:0.75);
    if(!navigationEnabled)return;finishDrag();const boundedSpan=clamp(span,Math.min(1,fullHi-fullLo),fullHi-fullLo);
    lo=clamp(center-boundedSpan*fraction,fullLo,fullHi-boundedSpan);hi=lo+boundedSpan;scheduleDraw();},{passive:false});
});
$('session').addEventListener('change',refresh);
$('reset').addEventListener('click',resetWindow);
$('more').addEventListener('click',()=>{if(data.event_insights)mlPage++;else mlLimit+=50;renderML();});
$('ml-prev').addEventListener('click',()=>{mlPage--;renderML();});
$('event-prev').addEventListener('click',()=>{eventPage--;renderEvents();});
$('event-next').addEventListener('click',()=>{eventPage++;renderEvents();});
window.addEventListener('resize',()=>{finishDrag();drawAll();});refresh();

// All untrusted diagnostics are text nodes, never markup.
function renderQuality(){
 const q=data.data_quality,target=$('quality-content');
 $('quality-status').textContent=!q?'Сведения о качестве данных недоступны.':q.status==='ok'?'Данные проверены. Существенных разрывов наблюдений не обнаружено.':q.long_gaps?'Есть разрывы наблюдений. Некоторые периоды могут быть проанализированы не полностью.':'Есть замечания к исходным данным. Подробности — в разделе ниже.';
 if(!q){el('p','Сведения о качестве данных недоступны.',target);return;}
 el('p',q.status==='ok'?'Проверки пройдены. Предупреждений не обнаружено.':'Есть замечания к данным; учитывайте их при интерпретации.',target,'notice');
 el('p',`${date(q.start_utc)} — ${date(q.end_utc)}`,target);
 const cards=el('div',undefined,target,'cards');
 [['Исходные CSV',q.source_csv_count],['Измерения',q.measurements],['Сессии сервера',q.sessions],['Длительные разрывы',q.long_gaps],['Максимальный интервал, с',q.max_interval_seconds]].forEach(([label,value])=>{const c=el('div',undefined,cards,'card');el('span',label,c);el('strong',num(value),c);});
 if(q.split?.method==='chronological')el('p',`Хронологическое разделение: обучение — ${measurements(q.split.training_measurements)}, проверка — ${measurements(q.split.evaluation_measurements)}. Последнее обучение: ${date(q.split.training_last_utc)}; начало проверки: ${date(q.split.evaluation_first_utc)}. Графики и детекторы показывают проверочный период.`,target);
 else el('p','Обучение и проверка — отдельные CSV. Качество данных показано для проверочного файла.',target);
 if(q.warnings.length)list('Предупреждения',q.warnings,target);
 list('Ограничения',q.limitations,target);
}
renderQuality();

for(const id of ['show-events','show-stat','show-ml'])$(id).addEventListener('change',drawAll);
function renderInterpretation(){
 const r=data.interpretation;if(!r){$('analysis-conclusion').textContent='Сводка интерпретации недоступна для этого отчёта.';return;}
 const metric=m=>m.evaluated?`${num(m.count,0)} из ${num(m.evaluated,0)} (${num(m.percent)} %)`:'Данные недоступны';
 const target=$('result-cards');
 const full=data.full_period,stat=full?{count:full.stat_anomalies,evaluated:full.stat_evaluable_measurements,percent:full.stat_evaluable_measurements?100*full.stat_anomalies/full.stat_evaluable_measurements:null}:r.statistical;
 for(const [label,m] of [['Необычные изменения · участок поиска',r.ml],['Резкие изменения MSPT · вся история',stat]]){
  const card=el('div',undefined,target,'card');el('span',label,card);el('strong',metric(m),card);
 }
 $('regime-note').textContent=r.coverage_warnings.length?'В этом периоде сервер работал в условиях, которые редко встречались ранее. Необычные изменения могут быть связаны с онлайном игроков, а не с лагами.':'';
 const scope=$('period-scope'),q=data.data_quality;
 if(q?.split?.method==='chronological')el('span',`Полный период наблюдения: ${measurements(q.measurements)}. `,scope);
 else el('span','Источники обучения и проверки — отдельные CSV; их периоды могут пересекаться. ',scope);
 el('span',`Период обучения: ${measurements(r.train_measurements)}. Проверочный период: ${measurements(r.test_measurements)}. Графики, показатели и пороговые события относятся ${data.full_period?.scope==='pilot_full'?'ко всей истории':'к проверочному файлу'}. ML-результаты — только к проверочному периоду. `,scope);
 el('span',`Только TEST: измерения с меткой хотя бы одного детектора: ${num(r.unique,0)}; совпадения: ${num(r.both,0)}.`,scope);
 const wrap=el('div',undefined,$('training-coverage'),'table-wrap'),table=el('table',undefined,wrap),head=el('tr',undefined,el('thead',undefined,table));
 ['Режим','Обучение (TRAIN)','Проверка (TEST)','ML-отклонения TEST'].forEach(v=>el('th',v,head));
 const body=el('tbody',undefined,table);
 r.coverage.forEach(row=>{const tr=el('tr',undefined,body);[row.label,metric(row.train),metric(row.test),metric(row.test_ml)].forEach(v=>el('td',v,tr));});
 if(r.coverage_warnings.length)list('Осторожная интерпретация',r.coverage_warnings,$('training-coverage'));
 el('p',`Диагностическая эвристика: режим есть в TEST, но составляет менее ${num(r.weak_coverage_percent)} % TRAIN. Это не универсальный порог репрезентативности и не оценка точности ML.`, $('training-coverage'),'muted');
}
renderInterpretation();
$('report-period').textContent=data.points.length?`Анализируемый период: ${date(time(data.points[0]))} — ${date(time(data.points.at(-1)))}`:RU.noData;

function renderML(){
 if(!data.event_insights)return renderRawML();
 const rows=data.event_insights.ml_episodes.filter(belongs),target=$('ml-list');target.replaceChildren();
 // Keep individual scores and source references in the existing technical disclosure.
 renderRawML(false);
 $('raw-more').hidden=rawML.length<=(rawPage+1)*50;$('raw-prev').hidden=rawPage===0;
 const start=mlPage===0?0:8+(mlPage-1)*50;
 const end=mlPage===0?8:start+50;
 $('more').hidden=rows.length<=end;$('ml-prev').hidden=mlPage===0;
 if(!rows.length){el('p','Необычных периодов не обнаружено',target,'empty');return;}
 rows.slice(start,end).forEach(e=>{
  const card=el('details',undefined,target),summary=el('summary',undefined,card);
  el('strong',e.threshold_signal?'Период необычной нагрузки':'Период необычного поведения',summary);
  el('span',`${date(e.start_utc)} — ${date(e.last_observed_utc)}`,summary);
  el('p',`MSPT: максимум ${num(e.peak_mspt)} мс, среднее ${num(e.mean_mspt)} мс · TPS: минимум ${num(e.min_tps)} · Игроки: ${num(e.players_min,0)}–${num(e.players_max,0)}`,card);
  el('p',`${measurements(e.measurements)} · ${e.single_observation?'Одиночное наблюдение':`Наблюдаемый охват: ${num(e.observed_span_seconds)} с`}`,card);
  const labels={entities_delta:'Изменение сущностей',loaded_chunks_delta:'Изменение загруженных чанков',gc_count_delta:'Прирост числа GC',gc_time_delta_ms:'Прирост накопленного времени GC, мс'};
  Object.entries(e.context).forEach(([key,v])=>el('p',`${labels[key]}: ${num(v.sum)}${key.startsWith('gc_')?'':` · максимальный положительный прирост ${num(v.max_positive_delta)}`} · доступно ${num(v.available,0)} наблюдений`,card));
  if(e.observed_facts.length)list('Что происходило',e.observed_facts,card);
  if(e.suggested_checks.length)list('Что стоит проверить',e.suggested_checks,card);
  el('p',e.limitation,card,'muted');
 });
 el('p',`Периоды: ${num(start+1,0)}–${num(Math.min(rows.length,end),0)} из ${num(rows.length,0)}`,target,'muted');
}
$('raw-more').addEventListener('click',()=>{rawPage++;renderML();});
$('raw-prev').addEventListener('click',()=>{rawPage--;renderML();});
const health=data.performance_health;
if(health){document.documentElement?.setAttribute('data-health',health.state);$('health-label').textContent=health.label;$('health-reason').textContent=health.reason;}
else{$('health-label').textContent='Недостаточно данных';}
