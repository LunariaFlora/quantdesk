'use strict';
const $ = id => document.getElementById(id);
const money = n => Number(n).toLocaleString('zh-CN', {minimumFractionDigits:2, maximumFractionDigits:2});
const pct = n => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
let csv = '', meta = {}, result = null, busy = false, revision = 0, dataRevision = 0, charts = [];
function status(text, error=false) { for(const id of ['status','status-top']){$(id).textContent=text; $(id).className=error?'error':'';} }
function dirty() {
  revision++;
  $('export').disabled=true;
  $('export-trades').disabled=true;
  if(result)$('outdated').hidden=false;
  if(result) status('参数或数据已修改，当前图表是上一次结果；请重新运行。');
}
function dataInfo() {
  $('data-info').textContent = `${meta.name} · ${meta.rows || '待校验'} 根日线\n${meta.start || ''} — ${meta.end || ''}\n${meta.price_basis}`;
  $('data-info').style.whiteSpace='pre-line';
}
async function sample() {
  const loading=++dataRevision;
  csv=''; dirty(); status('正在读取历史样本…');
  try {
    const response=await fetch('/api/data'); const data=await response.json();
    if(loading!==dataRevision)return;
    if(!response.ok) throw new Error(data.error);
    csv=data.csv;meta=data.meta;
    $('start').value=meta.start;$('end').value=meta.end;
    dataInfo();status(`${meta.rows} 根历史日线已就绪`);
  } catch(e) { if(loading!==dataRevision)return;status(e.message,true); $('data-info').textContent='样本不可用；可以导入自己的 CSV。'; }
}
$('dataset').addEventListener('change',async()=>{
  const custom=$('dataset').value==='custom';$('upload-wrap').hidden=!custom;
  if(custom){dataRevision++;csv='';meta={};$('upload').value='';$('start').value='';$('end').value='';$('data-info').textContent='选择文件后将在运行时校验。';dirty();status('请选择 CSV 文件');}
  else await sample();
});
$('upload').addEventListener('change',async()=>{
  const loading=++dataRevision;csv='';dirty();const file=$('upload').files[0];if(!file)return;
  if(file.size>3_000_000){status('文件超过 3 MB，请缩小数据范围。',true);return;}
  try{const text=await file.text();if(loading!==dataRevision)return;csv=text;meta={name:file.name,source:'用户本地 CSV',price_basis:'导入价格口径由用户确认；仅模拟价格变化。',currency:'数据计价单位'};dataInfo();status('文件已读取，运行回测时校验数据。');}
  catch(e){status('文件读取失败：'+e.message,true);}
});
$('form').addEventListener('input',e=>{if(e.target.id!=='upload')dirty();});
$('form').addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;if(!csv){status('请先选择有效的历史行情数据。',true);return;}
  if(+$('fast').value>=+$('slow').value){status('短均线周期必须小于长均线周期。',true);return;}
  busy=true;$('run').disabled=true;$('run-top').disabled=true;status('正在校验数据并计算…');
  const rev=revision, sourceMeta={...meta}, params=Object.fromEntries(new FormData($('form')));
  try {
    const response=await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv,params})});
    const data=await response.json();if(!response.ok)throw new Error(data.error);
    if(rev!==revision){status('计算期间参数已改变，请重新运行。');return;}
    Object.assign(meta,data.data_summary);Object.assign(sourceMeta,data.data_summary);dataInfo();
    if(!$('start').value)$('start').value=data.params.start;
    if(!$('end').value)$('end').value=data.params.end;
    result={...data,dataset:sourceMeta,generated_at:new Date().toISOString()};
    render();$('export').disabled=false;$('export-trades').disabled=false;
    status(`已完成 · ${data.summary.bars} 根日线 · ${data.summary.trades} 笔成交`);
  }catch(e){status(e.message,true);$('export').disabled=true;$('export-trades').disabled=true;}
  finally{busy=false;$('run').disabled=false;$('run-top').disabled=false;}
});
function render(){
  $('outdated').hidden=true;
  const s=result.summary, p=result.params;
  $('empty').hidden=true;$('result').hidden=false;
  $('result-name').textContent=`${result.dataset.name} / ${p.fast} · ${p.slow} 日均线`;
  $('range').textContent=`${result.curve[0].date} → ${result.curve.at(-1).date}`;
  for(const [id,n] of [['return',s.return_pct],['benchmark',s.benchmark_pct],['drawdown',s.max_drawdown_pct]]){
    $(id).textContent=pct(n);$(id).className=n>=0?'positive':'negative';
  }
  $('equity').textContent=`期末资产 ${money(s.equity)}`;$('trades-count').textContent=s.trades;
  $('fees').textContent=`累计手续费 ${money(s.fees)}`;
  $('execution').textContent=`${s.trading_start} 起交易 · ${p.slow} 根日线预热 · ${result.dataset.currency}`;
  $('position').textContent=`期末持有 ${s.shares} 股 · 现金 ${money(s.cash)} · 已平仓 ${s.closed_trades} 次`;
  $('source').textContent=`来源：${result.dataset.source}；${result.dataset.price_basis}`;
  const tbody=$('trade-rows');tbody.replaceChildren();
  for(const t of result.trades){
    const row=document.createElement('tr');
    for(const value of [t.signal_date,t.date,t.side,money(t.price),t.quantity,money(t.fee),money(t.cash)]){
      const cell=document.createElement('td');cell.textContent=value;
      if(value===t.side){const badge=document.createElement('span');badge.className=t.side==='买入'?'buy':'sell';badge.textContent=value;cell.replaceChildren(badge);cell.title=t.reason;}
      row.append(cell);
    }tbody.append(row);
  }
  $('no-trades').hidden=result.trades.length>0;
  charts=[{id:'equity-chart',readout:'equity-readout',lines:[['equity','策略','#2167c7',false],['benchmark','买入持有','#8b9bab',true]]},
    {id:'price-chart',readout:'price-readout',lines:[['close','收盘','#8b9bab',true],['fast','短均线','#2167c7',false],['slow','长均线','#c78b35',false]]}];
  for(const config of charts){draw(config);const c=$(config.id);
    c.onpointermove=e=>{const r=c.getBoundingClientRect();const idx=Math.round(Math.max(0,Math.min(1,(e.clientX-r.left-64)/(r.width-84)))*(result.curve.length-1));draw(config,idx);const row=result.curve[idx];$(config.readout).textContent=row.date+'  ·  '+config.lines.map(([k,l])=>`${l} ${row[k]===null?'预热中':money(row[k])}`).join('  /  ');};
    c.onpointerleave=()=>draw(config);
  }
}
function draw(config,hover=null){
  const c=$(config.id),ctx=c.getContext('2d'),rect=c.getBoundingClientRect();
  const w=rect.width,h=rect.height,dpr=window.devicePixelRatio||1;
  c.width=w*dpr;c.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
  const values=result.curve.flatMap(r=>config.lines.map(([k])=>r[k]).filter(v=>v!==null));
  let low=Math.min(...values),high=Math.max(...values);const pad=(high-low)*.12||1;low-=pad;high+=pad;
  const left=64,right=w-20,top=12,bottom=h-30;
  const x=i=>left+i/(result.curve.length-1)*(right-left),y=v=>bottom-(v-low)/(high-low)*(bottom-top);
  ctx.font='10px Segoe UI';ctx.fillStyle='#718696';ctx.strokeStyle='#edf1f5';ctx.lineWidth=1;
  for(let i=0;i<5;i++){const value=low+(high-low)*i/4,yy=y(value);ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();ctx.textAlign='right';ctx.fillText(value>=10000?(value/1000).toFixed(1)+'k':value.toFixed(1),left-10,yy+3);}
  const ticks=w<480?2:4;
  for(let i=0;i<ticks;i++){const idx=Math.round(i/(ticks-1)*(result.curve.length-1));ctx.textAlign=i===0?'left':i===ticks-1?'right':'center';ctx.fillText(result.curve[idx].date,x(idx),h-7);}
  for(const [key,,color,dashed] of config.lines){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=1.8;ctx.setLineDash(dashed?[4,4]:[]);let started=false;
    result.curve.forEach((row,i)=>{if(row[key]===null){started=false;return;}if(!started){ctx.moveTo(x(i),y(row[key]));started=true;}else ctx.lineTo(x(i),y(row[key]));});ctx.stroke();
  }ctx.setLineDash([]);
  if(hover!==null){ctx.strokeStyle='#cad6df';ctx.beginPath();ctx.moveTo(x(hover),top);ctx.lineTo(x(hover),bottom);ctx.stroke();for(const [key,,color]of config.lines){const v=result.curve[hover][key];if(v===null)continue;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x(hover),y(v),3.5,0,Math.PI*2);ctx.fill();}}
}
new ResizeObserver(()=>{if(result)charts.forEach(c=>draw(c));}).observe($('workspace'));
function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export').onclick=()=>{if(result)download('backtest-report.json',JSON.stringify({...result,assumptions:'原始价格；未计分红、拆股、税费或容量约束；期末持仓按收盘估值；收盘信号次日开盘执行。'},null,2),'application/json');};
$('export-trades').onclick=()=>{if(!result)return;const keys=['signal_date','date','side','price','quantity','fee','cash','reason'];download('trades.csv','\ufeff'+[keys.join(','),...result.trades.map(t=>keys.map(k=>t[k]).join(','))].join('\r\n'),'text/csv;charset=utf-8');};
sample();
