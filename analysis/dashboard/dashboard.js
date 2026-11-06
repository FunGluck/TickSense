'use strict';
// Presentation-only strings live here to allow another locale later.
const RU = {
  high_mspt:'Высокий MSPT',low_tps:'Низкий TPS',elevated_mspt:'Повышенный MSPT',
  measurements:'Измерения',sessions:'Сессии сервера',mean:'Средний MSPT',peak:'Максимальный MSPT',
  minimum:'Минимальный TPS',ml:'ML-отклонения',stat:'Статистические отклонения',episodes:'Пороговые эпизоды',
  noEvents:'Событий не обнаружено',noML:'ML-отклонений не обнаружено',noData:'Нет данных в выбранном диапазоне',
  unknown:'Данные недоступны',session:'Сессия',rows:'Исходные строки CSV',file:'Файл',
  loaded_chunks_delta:'Изменение числа загруженных чанков',entities_delta:'Изменение числа сущностей',
  gc_count_delta:'Прирост числа сборок GC',gc_time_delta_ms:'Прирост накопленного времени GC',heap_used_ratio:'Доля использованной выделенной памяти JVM',
  facts:'Наблюдаемые факты',interpretation:'Возможная интерпретация',limits:'Ограничения',context:'Числовой контекст',
  single:'Одиночное наблюдение',span:'Наблюдаемый охват',sum:'Сумма доступных интервальных приростов',
  net:'Сумма знаковых изменений',positive:'Максимальный положительный прирост',coverage:'Доступно наблюдений',
  score:'Оценка модели',time:'Время, UTC',start:'Начало',last:'Последнее наблюдение',
  more:'Показать ещё',allML:'Показаны все ML-отклонения'
};
const data=JSON.parse(document.getElementById('report-data').textContent);
const $=id=>document.getElementById(id), num=(n,d=2)=>n===null||n===undefined||!Number.isFinite(Number(n))?'—':new Intl.NumberFormat('ru-RU',{maximumFractionDigits:d}).format(n);
const plural=(n,forms)=>forms[(n%100>=11&&n%100<=14)?2:(n%10===1?0:(n%10>=2&&n%10<=4?1:2))];
const measurements=n=>`${num(n,0)} ${plural(n,['измерение','измерения','измерений'])}`;
const date=t=>t!==null&&t!==undefined?new Intl.DateTimeFormat('ru-RU',{timeZone:'UTC',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3}).format(new Date(t))+' UTC':'—';
const text=value=>String(value??'').replace(/(\d)\.(\d)/g,'$1,$2');
function el(tag,content,parent,cls){const n=document.createElement(tag);if(content!==undefined)n.textContent=content;if(cls)n.className=cls;if(parent)parent.append(n);return n;}
const sessions=[...new Set(data.points.map(p=>String(p.session_id)))];
sessions.forEach(s=>{const o=el('option',`${RU.session} ${s}`,$('session'));o.value=s;});
let points=[],events=[],lo=0,hi=1,fullLo=0,fullHi=1,mlLimit=50,navigationEnabled=false,drag=null;
const CANVAS_FONT='13px Inter, "Segoe UI", Arial, sans-serif';
const time=p=>Date.parse(p.timestamp_utc), belongs=x=>$('session').value==='all'||String(x.session_id)===$('session').value;
function refresh(){
  finishDrag();
  points=data.points.filter(belongs);events=data.events.filter(belongs);mlLimit=50;
  const times=points.map(time).filter(Number.isFinite);fullLo=times.length?Math.min(...times):0;fullHi=times.length?Math.max(...times):1;
  navigationEnabled=times.length>1&&fullHi>fullLo;
  // Axis padding for a single timestamp only; not an observed duration.
  if(fullHi===fullLo){fullLo-=500;fullHi+=500;}lo=fullLo;hi=fullHi;
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
  c.font=CANVAS_FONT;c.strokeStyle='#283246';c.fillStyle='#9baac0';
  for(let i=0;i<=4;i++){const v=max*i/4;c.beginPath();c.moveTo(52,y(v));c.lineTo(w-18,y(v));c.stroke();c.fillText(num(v,1),5,y(v)+4);}
  for(let i=0;i<3;i++){const t=lo+(hi-lo)*i/2,label=new Date(t).toLocaleTimeString('ru-RU',{timeZone:'UTC'});c.fillText(label,Math.min(w-70,Math.max(52,x(t)-25)),h-10);}
  // A change of session/file, missing value or backward timestamp breaks the path.
  c.strokeStyle='#7faeff';c.lineWidth=1.7;c.beginPath();let previous=null;
  rows.forEach(p=>{if(p[key]===null||!Number.isFinite(p[key])){previous=null;return;}
    if(!previous||p.session_id!==previous.session_id||p.source_file!==previous.source_file||time(p)-time(previous)>(data.data_quality?.max_gap_seconds??30)*1000||time(p)<time(previous))c.moveTo(x(time(p)),y(p[key]));
    else c.lineTo(x(time(p)),y(p[key]));previous=p;});c.stroke();
  const eventRows=new Set(events.flatMap(e=>e.source_rows.map(r=>`${e.session_id}|${e.source_file}|${r}`)));
  valid.forEach(p=>{const px=x(time(p)),py=y(p[key]);
    c.fillStyle='#7faeff';c.beginPath();c.arc(px,py,1.7,0,Math.PI*2);c.fill();
    if($('show-events').checked&&eventRows.has(`${p.session_id}|${p.source_file}|${p.csv_row}`)){c.strokeStyle='#77e1bb';c.lineWidth=1.6;c.strokeRect(px-5,py-5,10,10);}
    if($('show-stat').checked&&p.stat_anomaly){c.fillStyle='#ffbd66';c.beginPath();c.arc(px,py,3.5,0,Math.PI*2);c.fill();}
    if($('show-ml').checked&&p.ml_anomaly){c.strokeStyle='#fb83ae';c.lineWidth=2;c.beginPath();c.moveTo(px-4,py-4);c.lineTo(px+4,py+4);c.moveTo(px+4,py-4);c.lineTo(px-4,py+4);c.stroke();}
  });
  if(!valid.length)c.fillText(RU.noData,60,h/2);
  plotInfo[id]={rows:valid,x,y,width:w};
}
function drawAll(){draw('mspt','mspt_avg');draw('tps','tps_1m');drawNavigator();$('period').textContent=points.length?`${date(lo)} — ${date(hi)}`:RU.noData;$('tooltip').hidden=true;}
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
// Keep the handles distinguishable even on a narrow navigator (at least 24 CSS px).
const minWindow=()=>Math.min(fullHi-fullLo,Math.max(1,Math.ceil((fullHi-fullLo)*24/navigatorGeometry().width)));
// All input methods share these bounds and the same lo/hi for both plots.
function changeWindow(mode,delta,startLo=lo,startHi=hi){
  if(!navigationEnabled)return;
  if(mode==='left'){hi=startHi;lo=clamp(startLo+delta,fullLo,hi-minWindow());}
  else if(mode==='right'){lo=startLo;hi=clamp(startHi+delta,lo+minWindow(),fullHi);}
  else{const span=startHi-startLo;lo=clamp(startLo+delta,fullLo,fullHi-span);hi=lo+span;}
  drawAll();
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
  const bottom=r.height-24,valid=points.filter(p=>p.mspt_avg!==null&&Number.isFinite(p.mspt_avg)&&Number.isFinite(time(p)));
  const max=valid.reduce((v,p)=>Math.max(v,p.mspt_avg),1),y=v=>bottom-v/max*(bottom-12);
  c.strokeStyle='#7faeff';c.lineWidth=1.5;c.beginPath();let previous=null;
  points.forEach(p=>{if(p.mspt_avg===null||!Number.isFinite(p.mspt_avg)||!Number.isFinite(time(p))){previous=null;return;}
    if(!previous||p.session_id!==previous.session_id||p.source_file!==previous.source_file||time(p)-time(previous)>(data.data_quality?.max_gap_seconds??30)*1000||time(p)<time(previous))c.moveTo(navX(time(p)),y(p.mspt_avg));
    else c.lineTo(navX(time(p)),y(p.mspt_avg));previous=p;});c.stroke();
  const left=navX(lo),right=navX(hi),g=navigatorGeometry();
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
    const nearest=info.rows.reduce((best,p)=>{const distance=Math.hypot(info.x(time(p))-px,info.y(p[id==='mspt'?'mspt_avg':'tps_1m'])-py);return !best||distance<best.distance?{p,distance}:best;},null);
    if(!nearest){$('tooltip').hidden=true;return;}
    const p=nearest.p,signals=events.filter(v=>v.session_id===p.session_id&&v.source_file===p.source_file&&v.source_rows.includes(p.csv_row)).map(v=>RU[v.signal]);
    $('tooltip').textContent=[date(p.timestamp_utc),`${RU.session}: ${p.session_id} · ${RU.rows}: ${num(p.csv_row,0)}`,`MSPT: ${num(p.mspt_avg,3)} мс · TPS: ${num(p.tps_1m)}`,p.ml_anomaly?`${RU.ml} · ${RU.score}: ${num(p.anomaly_score,6)}`:null,p.stat_anomaly?`${RU.stat} · Локальный порог: ${num(p.rolling_threshold,3)} мс · Превышение: ${num(p.excess_mspt,3)} мс`:null,...signals].filter(Boolean).join('\n');
    $('tooltip').hidden=false;$('tooltip').style.left=Math.max(8,Math.min(e.clientX+16,window.innerWidth-370))+'px';$('tooltip').style.top=Math.max(8,Math.min(e.clientY+16,window.innerHeight-$('tooltip').offsetHeight-8))+'px';
  }
  canvas.addEventListener('pointermove',inspect);canvas.addEventListener('click',inspect);canvas.addEventListener('pointerleave',()=>$('tooltip').hidden=true);
  bindDrag(canvas,false);
  canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect(),fraction=Math.max(0,Math.min(1,(e.clientX-r.left-52)/(r.width-70))),center=lo+(hi-lo)*fraction,span=(hi-lo)*(e.deltaY>0?1.3:0.75);
    if(!navigationEnabled)return;finishDrag();const boundedSpan=clamp(span,minWindow(),fullHi-fullLo);
    lo=clamp(center-boundedSpan*fraction,fullLo,fullHi-boundedSpan);hi=lo+boundedSpan;drawAll();},{passive:false});
});
$('session').addEventListener('change',refresh);
$('reset').addEventListener('click',resetWindow);
$('more').addEventListener('click',()=>{mlLimit+=50;renderML();});
window.addEventListener('resize',()=>{finishDrag();if(navigationEnabled&&hi-lo<minWindow()){const span=minWindow();lo=clamp(lo,fullLo,fullHi-span);hi=lo+span;}drawAll();});refresh();

// All untrusted diagnostics are text nodes, never markup.
function renderQuality(){
 const q=data.data_quality,target=$('quality-content');
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
 for(const [label,value,description] of [
  ['Пороговые события',num(r.performance_events,0),'Эпизоды, удовлетворяющие настроенным условиям повышенной нагрузки или снижения TPS. Их число не равно числу независимых проблем.'],
  ['ML-отклонения',metric(r.ml),'Необычные состояния относительно обучающих данных.'],
  ['Статистические отклонения',metric(r.statistical),'MSPT выше среднего шести предыдущих измерений плюс три стандартных отклонения.']]){
  const card=el('div',undefined,target,'card');el('span',label,card);el('strong',value,card);el('p',description,card);
 }
 $('analysis-conclusion').textContent=r.conclusion;
 const scope=$('period-scope'),q=data.data_quality;
 if(q?.split?.method==='chronological')el('span',`Полный период наблюдения: ${measurements(q.measurements)}. `,scope);
 else el('span','Источники обучения и проверки — отдельные CSV; их периоды могут пересекаться. ',scope);
 el('span',`Период обучения: ${measurements(r.train_measurements)}. Проверочный период: ${measurements(r.test_measurements)}. Графики и ML-результаты относятся к проверочному периоду. `,scope);
 el('span',`Измерения с меткой хотя бы одного детектора: ${num(r.unique,0)}; совпадения: ${num(r.both,0)}.`,scope);
 const wrap=el('div',undefined,$('training-coverage'),'table-wrap'),table=el('table',undefined,wrap),head=el('tr',undefined,el('thead',undefined,table));
 ['Режим','Обучение (TRAIN)','Проверка (TEST)','ML-отклонения TEST'].forEach(v=>el('th',v,head));
 const body=el('tbody',undefined,table);
 r.coverage.forEach(row=>{const tr=el('tr',undefined,body);[row.label,metric(row.train),metric(row.test),metric(row.test_ml)].forEach(v=>el('td',v,tr));});
 if(r.coverage_warnings.length)list('Осторожная интерпретация',r.coverage_warnings,$('training-coverage'));
 el('p',`Диагностическая эвристика: режим есть в TEST, но составляет менее ${num(r.weak_coverage_percent)} % TRAIN. Это не универсальный порог репрезентативности и не оценка точности ML.`, $('training-coverage'),'muted');
}
renderInterpretation();
