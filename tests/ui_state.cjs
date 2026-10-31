const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup() {
  const elements = new Map();
  const values = {paper:'A1',orientation:'auto',dpi:'200',gsd:'0.25',margin:'8',title:'Test',sourceProfile:'dmp_1954'};
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id,{value:values[id],checked:false,textContent:'',children:[],replaceChildren(){this.textContent='';this.children=[];},append(child){this.children.push(child);}});
    return elements.get(id);
  },createElement(){return {};}};
  const ctx=vm.createContext({document,L:{drawLocal:{draw:{handlers:{rectangle:{tooltip:{}},simpleshape:{tooltip:{}}}},edit:{handlers:{edit:{tooltip:{}}}}}},setTimeout(){},clearTimeout(){}});
  const source=fs.readFileSync('app/static/app.js','utf8').replace(/boot\(\);\s*setInterval\(listJobs, 4000\);\s*$/, '');
  vm.runInContext(source,ctx);
  return {ctx,el:id=>document.getElementById(id),run:s=>vm.runInContext(s,ctx)};
}
test('invalid request replaces stale estimates and cannot export', async()=>{
  const {run,el}=setup();
  el('estimate').textContent='864 million pixels';
  await run('bbox=[571768,6220363,579768,6230363]; api=async()=>{throw Error("Invalid settings")}; refreshEstimate()');
  assert.equal(el('size').textContent,'8.00 × 10.00 km');
  assert.equal(el('bbox').value,'571768.00, 6220363.00, 579768.00, 6230363.00');
  assert.equal(el('estimate').textContent,'Invalid settings');
  run('previewKey=JSON.stringify({bbox,source_profile:$("sourceProfile").value}); $("checked").checked=true; updateStart()');
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

test('DPI menu offers full resolution and descending 50 DPI steps',()=>{
  const {run,el}=setup();
  el('dpi').value='full';run('dpiOptions(779.5)');
  assert.deepEqual(el('dpi').children.map(x=>x.value),['full',...Array.from({length:15},(_,i)=>String(750-i*50))]);
  assert.equal(el('dpi').value,'full');
  el('dpi').value='700';run('dpiOptions(779.5)');assert.equal(el('dpi').value,'700');
  run('dpiOptions(600)');assert.equal(el('dpi').value,'full');
  assert.equal(el('dpi').children[1].value,'550');
  run('dpiOptions(45)');assert.equal(el('dpi').children.length,1);
});

test('changing source clears preview approval, pixels and old map',async()=>{
  const {run,el}=setup();
  await run(`sources=[{id:'dmp_1954',period:'1954',available:true,default_mpp:.25,meters_per_pixel:[.25,.5,1]},
    {id:'lave_maalebordsblade',period:'1901–1971',provider:'KDS',available:true,default_mpp:1,meters_per_pixel:[.5,1,2,4]}];
    var removed=[]; map={removeLayer(x){removed.push(x)}}; historicalLayer='old';
    previewKey=JSON.stringify({bbox,source_profile:'dmp_1954'}); $('checked').checked=true; estimateValid=true;
    api=async()=>({width_px:10,height_px:10,tiles:1,disk_bytes:100,paper_mm:[594,841],effective_dpi:1});
    $('sourceProfile').value='lave_maalebordsblade'; $('sourceProfile').onchange()`);
  assert.equal(el('checked').checked,false);
  assert.equal(el('start').disabled,true);
  assert.equal(el('gsd').value,'1');
  assert.equal(run('previewKey'),'');
  assert.equal(run('historicalLayer'),null);
  assert.equal(run('removed[0]'),'old');
  assert.equal(run('job().source_profile'),'lave_maalebordsblade');
});

test('late preview cannot reappear after source changes away and back',async()=>{
  const {run,el}=setup();
  const pending=run(`var finishPreview; api=()=>new Promise(resolve=>finishPreview=resolve); $('previewButton').onclick()`);
  run(`$('sourceProfile').value='lave_maalebordsblade'; invalidate();
       $('sourceProfile').value='dmp_1954'; invalidate(); finishPreview({})`);
  await pending;
  assert.equal(run('previewKey'),'');
  assert.equal(el('checked').checked,false);
  assert.equal(el('start').disabled,true);
});
