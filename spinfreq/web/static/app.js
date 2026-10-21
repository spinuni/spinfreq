'use strict';
const $ = id => document.getElementById(id);
let presets = {}, selected = null, timer = null;
const scopes = {'periodic-fmr':'Periodic FMR: analytic uniform-mode checks; no finite edges.', 'prism-fmr':'Single-cell prism: Gilbert susceptibility check; no resolved spatial modes.', 'confined-skyrmion':'Confined skyrmion: matched 2 nm OOMMF example. Refine the mesh for quantitative continuum frequencies.'};
async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) { const body = await response.json(); throw new Error(body.detail || 'Request failed'); }
  return response.status === 204 ? null : response.json();
}
function loadPreset() {
  const c = structuredClone(presets[$('preset').value]);
  $('config').value = JSON.stringify(c, null, 2); $('scope').textContent = scopes[$('preset').value];
  for (const [id, value] of Object.entries({nx:c.nx,ny:c.ny,dx:c.dx_m*1e9,dy:c.dy_m*1e9,thickness:c.thickness_m*1e9,field:c.field_T[2],fmin:c.fmin_Hz/1e9,fmax:c.fmax_Hz/1e9,points:c.points,drive:c.drive_T[0]*1e6})) $(id).value = value;
}
function fieldConfig() {
  const c = JSON.parse($('config').value);
  const number = id => { const text = $(id).value.trim(); if (!text || !Number.isFinite(Number(text))) throw new Error('Enter a finite value for '+id); return Number(text); };
  c.nx=number('nx');c.ny=number('ny');c.dx_m=number('dx')*1e-9;c.dy_m=number('dy')*1e-9;c.thickness_m=number('thickness')*1e-9;
  c.field_T[2]=number('field');c.fmin_Hz=number('fmin')*1e9;c.fmax_Hz=number('fmax')*1e9;c.points=number('points');c.drive_T[0]=number('drive')*1e-6;
  return c;
}
async function refreshList() {
  const jobs = await api('/api/jobs'); $('jobs').replaceChildren();
  for (const job of jobs) { const button=document.createElement('button'); button.className='secondary';button.textContent=job.id.slice(0,8)+' · '+job.status;button.onclick=()=>watch(job.id);$('jobs').append(button); }
}
async function watch(id) { selected=id;clearTimeout(timer);$('error').textContent='';await poll(); }
async function poll() {
  try {
    const id=selected, job=await api('/api/jobs/'+id); if(id!==selected)return;
    $('status').textContent=job.status+(job.stage?' · '+job.stage:'')+(job.error?' · '+job.error:'');
    const pending=['queued','running'].includes(job.status);$('cancel').hidden=!pending;$('delete').hidden=pending;$('results').hidden=job.status!=='succeeded';
    if(job.status==='succeeded') {
      const base='/api/jobs/'+id+'/artifacts/';
      for(const [key,name] of Object.entries({spectrum:'spectrum.png',equilibrium:'equilibrium.png',mode:'mode.png'}))$(key).src=base+name;
      for(const [key,name] of Object.entries({zip:'results.zip',json:'summary.json',csv:'response.csv',ovf:'equilibrium.ovf'}))$(key).href=base+name;
      const summary=await api(base+'summary.json');
      $('diagnostics').textContent=`${summary.stability} within numerical checks · torque ${summary.torque_T.toExponential(2)} T · max δm ${summary.max_delta_m.toExponential(2)} · ${summary.wall_s.toFixed(2)} s. ${summary.validation_scope}`;
    }
    await refreshList();if(pending)timer=setTimeout(poll,500);
  } catch(error){$('error').textContent=error.message;}
}
async function run(useFields) {
  $('error').textContent='';
  try { const config=useFields?fieldConfig():JSON.parse($('config').value);$('config').value=JSON.stringify(config,null,2);
    const job=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});await watch(job.id);
  } catch(error){$('error').textContent=error.message;}
}
$('preset').onchange=loadPreset;$('run').onclick=()=>run(true);$('run-json').onclick=()=>run(false);
$('apply').onclick=()=>{try{$('config').value=JSON.stringify(fieldConfig(),null,2);$('error').textContent='';}catch(error){$('error').textContent=error.message;}};
$('cancel').onclick=async()=>{try{await api('/api/jobs/'+selected+'/cancel',{method:'POST'});await poll();}catch(error){$('error').textContent=error.message;}};
$('delete').onclick=async()=>{try{clearTimeout(timer);await api('/api/jobs/'+selected,{method:'DELETE'});selected=null;$('results').hidden=true;$('delete').hidden=true;$('status').textContent='Job deleted.';await refreshList();}catch(error){$('error').textContent=error.message;}};
(async()=>{try{presets=await api('/api/presets');for(const name of Object.keys(presets)){const option=document.createElement('option');option.value=name;option.textContent=name;$('preset').append(option);}loadPreset();await refreshList();}catch(error){$('error').textContent=error.message;}})();
