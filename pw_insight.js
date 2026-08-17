const { chromium } = require('playwright');
const path = require('path');
const FILE='file://'+path.resolve('1688数字营销工作台.html');
const EXE='C:/Users/Administrator/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
(async()=>{
  const errors=[];
  const b=await chromium.launch({executablePath:EXE,args:['--no-sandbox']});
  const p=await b.newPage({viewport:{width:1600,height:1000}});
  p.on('pageerror',e=>errors.push('PE:'+e.message));
  p.on('console',m=>{ if(m.type()==='error') errors.push('CE:'+m.text()); });
  await p.goto(FILE,{waitUntil:'load'});
  await p.waitForTimeout(1500);
  await p.click('.topnav button[data-view="insight"]');
  await p.waitForTimeout(900);
  const info=await p.evaluate(()=>{
    const vis=document.getElementById('insightView').style.display;
    const jstKpis=[...document.querySelectorAll('#insJstKpi .kpi')].map(k=>k.querySelector('.k').textContent+'='+k.querySelector('.v').textContent);
    const sygcKpis=[...document.querySelectorAll('#insSygcKpi .kpi')].map(k=>k.querySelector('.k').textContent+'='+k.querySelector('.v').textContent);
    const svg=!!document.querySelector('#insChart svg');
    const skuTable=document.querySelector('#insSkuBody table');
    const ths=skuTable?[...skuTable.querySelectorAll('thead th')].map(t=>t.textContent.trim()):[];
    const skuRows=skuTable?[...skuTable.querySelectorAll('tbody tr')].length:0;
    return {vis,jstKpis,sygcKpis,svg,ths,skuRows,year:document.getElementById('insYear').value,month:document.getElementById('insMonth').value};
  });
  console.log('insightView display=',JSON.stringify(info.vis),'(空=显示)');
  console.log('默认年/月=',info.year,'/',info.month);
  console.log('聚水潭卡片:',info.jstKpis);
  console.log('生意参谋卡片:',info.sygcKpis);
  console.log('趋势SVG存在=',info.svg);
  console.log('单品表列:',info.ths,'行数=',info.skuRows);

  await p.selectOption('#insMetric',{value:'refundRate'});
  await p.waitForTimeout(400);
  console.log('切换指标(退款率)后趋势SVG存在=',await p.evaluate(()=>!!document.querySelector('#insChart svg')));

  const fill=await p.evaluate(()=>{
    const tbl=document.querySelector('#insSkuBody table'); if(!tbl) return {};
    const ths=[...tbl.querySelectorAll('thead th')].map(t=>t.textContent.trim());
    const rows=[...tbl.querySelectorAll('tbody tr')];
    const out={};
    ths.forEach(n=>{ const i=ths.indexOf(n); let f=0,s=null; rows.forEach(r=>{const v=r.children[i]?.textContent.trim(); if(v&&v!=='—'){f++; if(!s)s=v;}}); out[n]={f,total:rows.length,s}; });
    return out;
  });
  console.log('单品表列填充：');
  Object.keys(fill).forEach(n=>console.log('  ',n,'填充',fill[n].f+'/'+fill[n].total,'样例',fill[n].s));

  await p.selectOption('#insYear',{value:'2025'});
  await p.waitForTimeout(200);
  await p.selectOption('#insMonth',{value:'06'});
  await p.waitForTimeout(500);
  const y2025=await p.evaluate(()=>({
    jst:[...document.querySelectorAll('#insJstKpi .kpi')].map(k=>k.querySelector('.k').textContent+'='+k.querySelector('.v').textContent),
    sygc:[...document.querySelectorAll('#insSygcKpi .kpi')].map(k=>k.querySelector('.k').textContent+'='+k.querySelector('.v').textContent),
    skuRows:document.querySelector('#insSkuBody table')?[...document.querySelectorAll('#insSkuBody table tbody tr')].length:0
  }));
  console.log('2025-06 聚水潭卡片:',y2025.jst);
  console.log('2025-06 生意参谋卡片(应为0/—):',y2025.sygc);
  console.log('2025-06 单品行数:',y2025.skuRows);

  console.log('\n=== JS 错误数:', errors.length, '===');
  errors.slice(0,15).forEach(e=>console.log(e));
  await b.close();
})().catch(e=>{ console.error('FATAL',e); process.exit(1); });
