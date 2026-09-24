import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const data = window.REVIEW;
const el = id => document.getElementById(id);
const names = Object.keys(data.parents);
const scene = new THREE.Scene();
scene.background = new THREE.Color('#101723');
const camera = new THREE.PerspectiveCamera(45, 1, 1, 100000);
camera.up.set(0, 0, 1);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
el('scene').appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
const v = a => new THREE.Vector3(...a);
function makeLine(color) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(6), 3));
  const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({color}));
  line.frustumCulled = false;
  scene.add(line);
  return line;
}
function place(line, a, b, visible) {
  line.visible = Boolean(visible && a && b);
  if (!line.visible) return;
  line.geometry.attributes.position.array.set([...a, ...b]);
  line.geometry.attributes.position.needsUpdate = true;
}
const independent = Object.fromEntries(names.map(n => [n, makeLine(0xffa860)]));
const connected = Object.fromEntries(names.map(n => [n, makeLine(0x00e5ff)]));
const axes = [0xff5555,0x66ff88,0x6699ff].map(makeLine);
const pointGeometry = new THREE.BufferGeometry();
pointGeometry.setAttribute('position', new THREE.Float32BufferAttribute(
  new Float32Array(Math.max(...data.frames.map(f => Object.keys(f.points).length)) * 3), 3));
const points = new THREE.Points(pointGeometry, new THREE.PointsMaterial({color:0xffdd66, size:5, sizeAttenuation:false}));
points.frustumCulled = false;
scene.add(points);
// Allocate marker geometry and labels once; missing observations hide both.
function shoulderMarker(label, color) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(5, 12, 8), new THREE.MeshBasicMaterial({color}));
  const canvas = document.createElement('canvas'); canvas.width=256; canvas.height=40;
  const ctx=canvas.getContext('2d'); ctx.fillStyle='#101723'; ctx.fillRect(0,0,256,40);
  ctx.font='22px system-ui'; ctx.fillStyle='#'+color.toString(16).padStart(6,'0'); ctx.fillText(label,6,28);
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas), depthTest:false}));
  sprite.scale.set(150,24,1); sprite.center.set(0,0);
  scene.add(mesh,sprite);
  return {mesh,sprite};
}
const shoulderMarkers={
  left:shoulderMarker('L shoulder',0xffffff), right:shoulderMarker('R shoulder',0xffffff),
  midpoint:shoulderMarker('Shoulder midpoint',0xffffff),
  leftMapped:shoulderMarker('L mapped SC',0xff66dd), rightMapped:shoulderMarker('R mapped SC',0xff66dd),
  leftConnected:shoulderMarker('L connected SC',0x00e5ff), rightConnected:shoulderMarker('R connected SC',0x00e5ff),
};
const shoulderLine=makeLine(0xffffff);
const shoulderGaps={left:makeLine(0xff66dd),right:makeLine(0xff66dd)};
function shoulderPositions(f) {
  const left=f.shoulder_keypoints?.left_shoulder, right=f.shoulder_keypoints?.right_shoulder;
  return {left,right,midpoint:left&&right?left.map((x,i)=>(x+right[i])/2):null,
    leftMapped:f.points.left_sternoclavicular,rightMapped:f.points.right_sternoclavicular,
    leftConnected:f.segments.left_clavicle?.connected_origin,rightConnected:f.segments.right_clavicle?.connected_origin};
}
function drawShoulders(f) {
  const p=shoulderPositions(f);
  for(const [key,marker] of Object.entries(shoulderMarkers)) {
    const group=key.endsWith('Mapped')?'shoulderMapped':key.endsWith('Connected')?'shoulderConnected':'shoulderObserved';
    marker.mesh.visible=Boolean(p[key]&&el(group).checked);
    marker.sprite.visible=marker.mesh.visible&&el('shoulderLabels').checked;
    if(p[key]) {marker.mesh.position.copy(v(p[key]));marker.sprite.position.copy(v(p[key])).add(new THREE.Vector3(0,0,8));}
  }
  place(shoulderLine,p.left,p.right,el('shoulderObserved').checked);
  const distance=(a,b)=>a&&b?v(a).distanceTo(v(b)).toFixed(1)+' mm':'unavailable';
  const rows=[];
  for(const side of ['left','right']) {
    const mapped=p[side+'Mapped'], connected=p[side+'Connected'];
    place(shoulderGaps[side],mapped,connected,el('shoulderGaps').checked);
    rows.push(`${side} SC gap: ${distance(mapped,connected)}`);
  }
  rows.push(`Shoulder width: ${distance(p.left,p.right)}`);
  rows.push(`Mapped SC width: ${distance(p.leftMapped,p.rightMapped)}`);
  rows.push(`Connected SC width: ${distance(p.leftConnected,p.rightConnected)}`);
  rows.push(`Midpoint to connected neck: ${distance(p.midpoint,f.segments.cervical_spine?.connected_origin)}`);
  el('shoulderStats').textContent=rows.join('\n');
}
names.forEach(n => {const option = document.createElement('option'); option.textContent = option.value = n; el('segment').appendChild(option);});
el('segment').value = names.includes('thoracic') ? 'thoracic' : names[0];
el('coverage').textContent = JSON.stringify(data.coverage,null,2);
el('provenance').textContent = JSON.stringify(data.provenance,null,2);
let index = Math.floor(data.frames.length * 0.75), playing = false, accumulated = 0;
el('frame').min=0; el('frame').max=data.frames.length-1;
el('start').max=el('end').max=data.frames.length-1;
el('start').value=index; el('end').value=data.frames.length-1;
function windowBounds() {
  let first = Number(el('start').value), last=Number(el('end').value);
  first = Math.max(0,Math.min(data.frames.length-1,Math.trunc(first)||0));
  last = Math.max(first,Math.min(data.frames.length-1,Math.trunc(last)||0));
  el('start').value=first; el('end').value=last;
  return [first,last];
}
function draw() {
  const f=data.frames[index];
  drawShoulders(f);
  let shown=0;
  for (const n of names) {
    const s=f.segments[n];
    place(independent[n],s?.origin,s?.end,el('independent').checked);
    place(connected[n],s?.connected_origin,s?.connected_end,el('connected').checked);
    if (s?.connected_origin) shown++;
  }
  const coordinates = Object.values(f.points);
  pointGeometry.attributes.position.array.set(coordinates.flat());
  pointGeometry.attributes.position.needsUpdate = true;
  pointGeometry.setDrawRange(0, coordinates.length);
  points.visible=el('points').checked;
  const n=el('segment').value, selected=f.segments[n];
  axes.forEach((axis,k) => {
    const origin = selected?.connected_origin || selected?.origin;
    const end = origin && selected ? origin.map((x,j) => x+70*selected.axes[k][j]) : null;
    place(axis,origin,end,el('axes').checked);
  });
  let step='unavailable';
  const previous=index>0?data.frames[index-1].segments[n]:null;
  if (selected && previous) {
    const dot=selected.axes.flat().reduce((sum,x,i)=>sum+x*previous.axes.flat()[i],0);
    step=(Math.acos(Math.max(-1,Math.min(1,(dot-1)/2)))*180/Math.PI).toFixed(2)+'°';
  }
  el('stats').textContent = `${shown}/${names.length} connected segments. ${n}: origin displacement ${selected?.shift_mm == null ? 'unavailable' : selected.shift_mm.toFixed(1)+' mm'}; rotation step ${step}.`;
  el('clock').textContent=`Sample index ${index} · saved frame ${f.number} · ${(f.time-data.frames[0].time).toFixed(3)} s`;
  el('frame').value=index;
}
function fitView() {
  const coordinates=Object.values(data.frames[index].points);
  if (!coordinates.length) return;
  const median = values => values.sort((a,b)=>a-b)[Math.floor(values.length/2)];
  const center=[0,1,2].map(k=>median(coordinates.map(p=>p[k])));
  // Robust framing avoids a single mistracked point moving the camera miles away.
  const radius=Math.max(700,median(coordinates.map(p=>v(p).distanceTo(v(center))))*2.5);
  controls.target.copy(v(center));
  camera.position.copy(v(center)).add(new THREE.Vector3(radius,radius,radius*0.5));
  controls.update();
}
el('frame').oninput=()=>{index=Number(el('frame').value); playing=false;el('play').textContent='Play';accumulated=0;draw();};
el('play').onclick=()=>{playing=!playing;el('play').textContent=playing?'Pause':'Play';accumulated=0;};
for (const id of ['start','end']) el(id).onchange=()=>{const [a,b]=windowBounds();index=Math.max(a,Math.min(b,index));accumulated=0;draw();};
for (const id of ['points','independent','connected','axes','segment']) el(id).onchange=draw;
for (const id of ['shoulderObserved','shoulderMapped','shoulderConnected','shoulderGaps','shoulderLabels']) el(id).onchange=draw;
el('shoulderView').onclick=()=>{
  const p=shoulderPositions(data.frames[index]);
  if(!p.midpoint) return;
  const radius=Math.max(400,v(p.left).distanceTo(v(p.right))*1.5);
  controls.target.copy(v(p.midpoint));
  camera.position.copy(v(p.midpoint)).add(new THREE.Vector3(radius,radius,radius*.25));
  for(const id of ['points','independent','axes']) el(id).checked=false;
  controls.update();draw();
};
el('all').onclick=()=>{el('start').value=0;el('end').value=data.frames.length-1;index=0;accumulated=0;draw();fitView();};
el('late').onclick=()=>{index=Math.floor(data.frames.length*.75);el('start').value=index;el('end').value=data.frames.length-1;accumulated=0;draw();fitView();};
el('resetView').onclick=fitView;
new ResizeObserver(()=>{const box=el('scene').getBoundingClientRect();renderer.setSize(box.width,box.height);camera.aspect=box.width/box.height;camera.updateProjectionMatrix();}).observe(el('scene'));
let previousTime;
function frameDuration(index, last) {
  if (index < last) return data.frames[index+1].time-data.frames[index].time;
  if (index > 0) return data.frames[index].time-data.frames[index-1].time;
  return data.frames.length > 1 ? data.frames[1].time-data.frames[0].time : Infinity;
}
function animate(time) {
  requestAnimationFrame(animate);
  const dt=previousTime == null?0:Math.min((time-previousTime)/1000,.25);previousTime=time;
  if (playing) {
    const [first,last]=windowBounds();
    if(index<first||index>last) index=first;
    accumulated+=dt;
    let duration=frameDuration(index,last);
    while(accumulated>=duration && duration>0) {
      accumulated-=duration;index=index<last?index+1:first;
      duration=frameDuration(index,last);
    }
    draw();
  }
  controls.update();renderer.render(scene,camera);
}
draw();fitView();requestAnimationFrame(animate);
