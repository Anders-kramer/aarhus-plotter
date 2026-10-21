const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup() {
  const elements = new Map();
  const values = {paper:'A1',orientation:'auto',dpi:'200',gsd:'0.25',margin:'8',title:'Test'};
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id,{value:values[id],checked:false,textContent:'',replaceChildren(){this.textContent='';},append(){}});
    return elements.get(id);
  },createElement(){return {};}};
  const ctx=vm.createContext({document,L:{drawLocal:{draw:{handlers:{rectangle:{tooltip:{}},simpleshape:{tooltip:{}}}},edit:{handlers:{edit:{tooltip:{}}}}}},setTimeout(){},clearTimeout(){}});
  const source=fs.readFileSync('app/static/app.js','utf8').replace(/boot\(\);\s*setInterval\(listJobs, 4000\);\s*$/, '');
  vm.runInContext(source,ctx);
  return {ctx,el:id=>document.getElementById(id),run:s=>vm.runInContext(s,ctx)};
}
test('oversized edited rectangle replaces stale estimates and cannot export', async()=>{
  const {run,el}=setup();
  el('estimate').textContent='864 million pixels';
  await run('bbox=[571768,6220363,579768,6230363]; api=async()=>{throw Error("Too many pixels")}; refreshEstimate()');
  assert.equal(el('size').textContent,'8.00 × 10.00 km');
  assert.equal(el('bbox').value,'571768.00, 6220363.00, 579768.00, 6230363.00');
  assert.equal(el('estimate').textContent,'Too many pixels');
  run('previewKey=JSON.stringify(bbox); $("checked").checked=true; updateStart()');
  assert.equal(el('start').disabled,true);
  await run('$("gsd").value="0.5"; api=async()=>({width_px:16000,height_px:20000,tiles:320,disk_bytes:1e9,paper_mm:[594,841],effective_dpi:100}); refreshEstimate()');
  assert.equal(el('start').disabled,false);
});
test('late invalid estimate cannot overwrite a newer valid selection',async()=>{
  const {run,el}=setup();
  const old=run('var rejectOld; api=()=>new Promise((_,reject)=>rejectOld=reject); refreshEstimate()');
  await run('api=async()=>({width_px:10,height_px:10,tiles:1,disk_bytes:100,paper_mm:[594,841],effective_dpi:1}); refreshEstimate()');
  run('rejectOld(Error("stale failure"))');await old;
  assert.notEqual(el('estimate').textContent,'stale failure');
  assert.equal(run('estimateValid'),true);
});
