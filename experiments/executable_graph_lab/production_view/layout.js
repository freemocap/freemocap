// Layered layout copied from the preserved synthetic viewer; presentation only.
function computeLayout(nodes,edges){
 const side=direction==='right',DUMMY=8,MARGIN=48,MAIN_GAP=side?128:100,CROSS_GAP=side?28:40;
 const byId=new Map(nodes.map(n=>[n.id,n])),geo=new Map(nodes.map(n=>[n.id,geometry(n)]));
 const parents=new Map(nodes.map(n=>[n.id,[]])),children=new Map(nodes.map(n=>[n.id,[]]));
 for(const e of edges){if(!byId.has(e.source)||!byId.has(e.target))throw Error(`Edge ${e.id} references an unknown node`);parents.get(e.target).push(e.source);children.get(e.source).push(e.target)}
 const rank=new Map();
 const visit=(id,stack)=>{if(rank.has(id))return rank.get(id);if(stack.has(id))throw Error('Backend graph contains a cycle');const next=new Set(stack).add(id),ps=parents.get(id);const r=ps.length?1+Math.max(...ps.map(p=>visit(p,next))):0;rank.set(id,r);return r};
 nodes.forEach(n=>visit(n.id,new Set()));
 // Pull producers forward so they sit beside their earliest consumer.
 for(const n of [...nodes].sort((a,b)=>rank.get(b.id)-rank.get(a.id))){const kids=children.get(n.id);if(kids.length)rank.set(n.id,Math.min(...kids.map(k=>rank.get(k)))-1)}
 const portCross=(id,key)=>{const p=geo.get(id).ports.get(key);if(!p)throw Error(`Missing declared slot ${key} on ${id}`);return side?p.y:p.x};
 const items=new Map();
 nodes.forEach((n,i)=>{const g=geo.get(n.id);items.set(n.id,{id:n.id,rank:rank.get(n.id),dummy:false,main:side?g.w:g.h,cross:side?g.h:g.w,key:[n.camera??-1,i]})});
 const chains=[],links=[];
 edges.forEach((e,ei)=>{const chain=[e.source];for(let r=rank.get(e.source)+1;r<rank.get(e.target);r++){const id=`~${e.id}~${r}`;items.set(id,{id,rank:r,dummy:true,main:0,cross:DUMMY,key:[byId.get(e.target).camera??-1,nodes.length+ei]});chain.push(id)}chain.push(e.target);chains.push({edge:e,chain});
  for(let i=0;i<chain.length-1;i++)links.push({a:chain[i],b:chain[i+1],aOff:i===0?portCross(e.source,'out:'+e.source_slot):DUMMY/2,bOff:i===chain.length-2?portCross(e.target,'in:'+e.target_slot):DUMMY/2})});
 const maxRank=Math.max(...[...items.values()].map(it=>it.rank));
 let layers=Array.from({length:maxRank+1},()=>[]);
 [...items.values()].sort((a,b)=>a.key[0]-b.key[0]||a.key[1]-b.key[1]).forEach(it=>layers[it.rank].push(it.id));
 const up=new Map(),down=new Map(),push=(m,k,v)=>{if(!m.has(k))m.set(k,[]);m.get(k).push(v)};
 for(const l of links){push(down,l.a,{o:l.b,self:l.aOff,other:l.bOff});push(up,l.b,{o:l.a,self:l.bOff,other:l.aOff})}
 const pos=new Map(),index=()=>layers.forEach(L=>L.forEach((id,i)=>pos.set(id,i)));
 const frac=(id,off)=>off/items.get(id).cross;
 const sweep=(r,m)=>{const L=layers[r],bc=new Map(L.map(id=>{const ns=m.get(id)||[];return [id,ns.length?ns.reduce((s,nb)=>s+pos.get(nb.o)+frac(nb.o,nb.other),0)/ns.length:pos.get(id)+.5]}));L.sort((a,b)=>bc.get(a)-bc.get(b));L.forEach((id,i)=>pos.set(id,i))};
 const crossings=()=>{let c=0;for(let r=0;r<maxRank;r++){const ls=links.filter(l=>items.get(l.a).rank===r).map(l=>[pos.get(l.a)+frac(l.a,l.aOff),pos.get(l.b)+frac(l.b,l.bOff)]);for(let i=0;i<ls.length;i++)for(let j=i+1;j<ls.length;j++)if((ls[i][0]-ls[j][0])*(ls[i][1]-ls[j][1])<0)c++}return c};
 index();let best=layers.map(L=>[...L]),bestC=crossings();
 for(let it=0;it<16&&bestC>0;it++){if(it%2===0)for(let r=1;r<=maxRank;r++)sweep(r,up);else for(let r=maxRank-1;r>=0;r--)sweep(r,down);const c=crossings();if(c<bestC){bestC=c;best=layers.map(L=>[...L])}}
 layers=best;index();
 // Cross-axis placement: pull each item toward its neighbours' ports while keeping order and gaps.
 const cross=new Map(),size=id=>items.get(id).cross;
 const gap=(a,b)=>items.get(a).dummy&&items.get(b).dummy?10:items.get(a).dummy||items.get(b).dummy?18:CROSS_GAP;
 layers.forEach(L=>{let y=0;const d=L.map((id,i)=>{const v=y;y+=size(id)+(i<L.length-1?gap(id,L[i+1]):0);return v});L.forEach((id,i)=>cross.set(id,d[i]-y/2))});
 const place=(L,want)=>{const n=L.length,f=[],b=[],out=[];
  for(let i=0;i<n;i++)f[i]=i?Math.max(want[i],f[i-1]+size(L[i-1])+gap(L[i-1],L[i])):want[i];
  for(let i=n-1;i>=0;i--)b[i]=i<n-1?Math.min(want[i],b[i+1]-size(L[i])-gap(L[i],L[i+1])):want[i];
  for(let i=0;i<n;i++){const a=(f[i]+b[i])/2;out[i]=i?Math.max(a,out[i-1]+size(L[i-1])+gap(L[i-1],L[i])):a}
  L.forEach((id,i)=>cross.set(id,out[i]))};
 const want=(id,maps)=>{let s=0,k=0;for(const m of maps)for(const nb of m.get(id)||[]){s+=cross.get(nb.o)+nb.other-nb.self;k++}return k?s/k:cross.get(id)};
 for(let it=0;it<28;it++){const maps=it<18?(it%2?[down]:[up]):[up,down],order=it%2?[...layers.keys()].reverse():[...layers.keys()];for(const r of order){const L=layers[r];place(L,L.map(id=>want(id,maps)))}}
 const layerSize=layers.map(L=>Math.max(0,...L.map(id=>items.get(id).main))),layerPos=[];let m=MARGIN;
 layerSize.forEach((s,r)=>{layerPos[r]=m;m+=s+MAIN_GAP});
 const totalMain=m-MAIN_GAP+MARGIN;
 let lo=Infinity,hi=-Infinity;for(const [id,c] of cross){lo=Math.min(lo,c);hi=Math.max(hi,c+size(id))}
 const shift=MARGIN-lo,totalCross=hi-lo+2*MARGIN,pt=(a,c)=>side?{x:a,y:c}:{x:c,y:a};
 const boxes=new Map();
 for(const n of nodes){const it=items.get(n.id),g=geo.get(n.id),p=pt(layerPos[it.rank],cross.get(n.id)+shift);boxes.set(n.id,{x:p.x,y:p.y,w:g.w,h:g.h,g})}
 const portAbs=(id,key)=>{const b=boxes.get(id),p=b.g.ports.get(key);if(!p)throw Error(`Missing declared slot ${key} on ${id}`);return {x:b.x+p.x,y:b.y+p.y}};
 const r1=v=>Math.round(v*10)/10;
 const curve=(p,q)=>{if(side){const k=Math.max(28,(q.x-p.x)*.5);return ` C${r1(p.x+k)},${r1(p.y)} ${r1(q.x-k)},${r1(q.y)} ${r1(q.x)},${r1(q.y)}`}const k=Math.max(28,(q.y-p.y)*.5);return ` C${r1(p.x)},${r1(p.y+k)} ${r1(q.x)},${r1(q.y-k)} ${r1(q.x)},${r1(q.y)}`};
 const paths=chains.map(({edge,chain})=>{let cur=portAbs(edge.source,'out:'+edge.source_slot),d=`M${r1(cur.x)},${r1(cur.y)}`;
  for(const id of chain.slice(1,-1)){const r=items.get(id).rank,c=cross.get(id)+shift+DUMMY/2,entry=pt(layerPos[r],c),exit=pt(layerPos[r]+layerSize[r],c);d+=curve(cur,entry);if(layerSize[r])d+=` L${r1(exit.x)},${r1(exit.y)}`;cur=exit}
  d+=curve(cur,portAbs(edge.target,'in:'+edge.target_slot));return {edge,d}});
 return {boxes,paths,width:side?totalMain:totalCross,height:side?totalCross:totalMain};
}

