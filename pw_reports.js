const { chromium } = require('playwright');
const path = require('path');
const FILE='file://'+path.resolve('1688数字营销工作台.html');
const EXE='C:/Users/Administrator/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

function colStats(tableSel){
  return (()=>{
    const tbl=document.querySelector(tableSel+' table');
    if(!tbl) return {ok:false, reason:'no table'};
    const ths=[...tbl.querySelectorAll('thead th')].map(t=>t.textContent.trim());
    const rows=[...tbl.querySelectorAll('tbody tr')];
    const want=['真实销售额','退款金额','退款率','销售毛利率','访客数','推广访客占比','展现量','广告点击量','点击率(参谋)','加购数(参谋)','加购率(参谋)','支付买家数','转化率(参谋)'];
    const res={};
    want.forEach(name=>{
      const i=ths.indexOf(name);
      if(i<0){ res[name]={col:false}; return; }
      let filled=0, sample=null;
      rows.forEach(r=>{ const td=r.children[i]; const v=(td?td.textContent.trim():''); if(v && v!=='—'){ filled++; if(!sample) sample=v; } });
      res[name]={col:true, filled, total:rows.length, sample};
    });
    return {ok:true, ths, res, rows:rows.length};
  })();
}

(async()=>{
  const errors=[];
  const b=await chromium.launch({executablePath:EXE,args:['--no-sandbox']});
  const p=await b.newPage({viewport:{width:1600,height:1000}});
  p.on('pageerror',e=>errors.push('PE:'+e.message));
  p.on('console',m=>{ if(m.type()==='error') errors.push('CE:'+m.text()); });
  await p.goto(FILE,{waitUntil:'load'});
  await p.waitForTimeout(1500);
  // 全局日期筛选设为「全部」，确保周报/月报覆盖全量数据
  await p.click('.qr[data-r="all"]').catch(()=>{});
  await p.waitForTimeout(300);

  // 1) 天气默认 华东 + 当月
  await p.click('.topnav button[data-view="weather"]');
  await p.waitForTimeout(700);
  const wx=await p.evaluate(()=>({region:document.getElementById('wxRegion').value, month:document.getElementById('wxMonth').value, year:document.getElementById('wxYear').value}));
  console.log('【天气默认】 region=',wx.region,'| month=',wx.month,'| year=',wx.year, '=>', (wx.region==='华东'&&wx.month==='08')?'PASS':'FAIL');

  // 2) 周报
  await p.click('.topnav button[data-view="weekly"]');
  await p.waitForTimeout(800);
  const wk=await p.evaluate(colStats, '#weeklyBody');
  console.log('\n【周报】 行数=',wk.rows, ' 列填充情况：');
  if(wk.ok) Object.keys(wk.res).forEach(n=>{ const r=wk.res[n]; console.log('  ', n, r.col?(`有列 填充 ${r.filled}/${r.total} 样例:${r.sample}`):'无此列'); });

  // 3) 月报
  await p.click('.topnav button[data-view="monthly"]');
  await p.waitForTimeout(800);
  const mo=await p.evaluate(colStats, '#monthlyBody');
  console.log('\n【月报】 行数=',mo.rows, ' 列填充情况：');
  if(mo.ok) Object.keys(mo.res).forEach(n=>{ const r=mo.res[n]; console.log('  ', n, r.col?(`有列 填充 ${r.filled}/${r.total} 样例:${r.sample}`):'无此列'); });

  // 月报 SKU 表
  const moSku=await p.evaluate(colStats, '#monthlySkuBody');
  console.log('\n【月报·单品表】 行数=',moSku.rows);
  if(moSku.ok) ['真实销售额','退款率','销售毛利率','访客数','点击率(参谋)','转化率(参谋)'].forEach(n=>{ const r=moSku.res[n]; console.log('  ', n, r.col?(`有列 填充 ${r.filled}/${r.total} 样例:${r.sample}`):'无此列'); });

  console.log('\n=== JS 错误数:', errors.length, '===');
  errors.slice(0,15).forEach(e=>console.log(e));
  await b.close();
})().catch(e=>{ console.error('FATAL',e); process.exit(1); });
