"""Loopback execution controls and projection for the shared Graph Lab viewer.

Projects exported executable work into logical/camera views. No authored edges,
The controller owns real execution; the projection never authors connections.
"""
from collections import Counter
from copy import deepcopy
import json


def project(definition, snapshot, summary=None):
    if snapshot['graph_digest'] != definition['digest']:
        raise ValueError('Snapshot and executable graph identity disagree')
    work = definition['work']
    by_work = {w['id']: w for w in work}
    if set(snapshot['states']) != set(by_work): raise ValueError('Snapshot work identities disagree')
    cameras = definition['cameras']
    def partition(w):
        return f"{w['node']}@{cameras.index(w['camera'])}" if w['camera'] is not None else w['node']
    nodes, partitions, edges, partition_edges = [], [], [], []
    states, partition_states = [], []
    for original in definition['nodes']:
        node = deepcopy(original)
        items = [w for w in work if w['node']==node['id']]
        indices = list(range(len(cameras))) if node['scope']=='camera_frame' else [None]
        node.update(handler=node['id'], branch='science', partition_count=len(indices), work_count=len(items),
                    description=node.get('description') or 'Real core operation. Input bindings and work keys come from the executable graph.',
                    resource_uses=[dict(name=node['id'], scope='camera' if node['scope']=='camera_frame' else 'recording')]
                        if node.get('lifetime_users') else [])
        if node.get('admission_window'):
            node['description'] += f" Load-ahead limit: {node['admission_window']['frames']} frames ahead of {node['admission_window']['consumer']}."
        nodes.append(node)
        for index in [None, *indices] if indices!=[None] else [None]:
            selected = items if index is None else [w for w in items if w['camera']==cameras[index]]
            counts = Counter(snapshot['states'][w['id']] for w in selected)
            state = next((s for s in ('failed','running','blocked','cancelled','pending') if counts[s]),'complete')
            timing = snapshot['timings'][node['id']]
            reasons = Counter()
            for w in selected:
                if snapshot['states'][w['id']]!='pending': continue
                missing = [d for _,ids in w['inputs'] for d in ids if snapshot['states'][d]!='complete']
                reason = 'waiting for input' if missing else 'waiting for ordering' if w['predecessor'] and snapshot['states'][w['predecessor']]!='complete' else 'awaiting admission (capacity/window)'
                reasons[reason] += 1
            if snapshot.get('paused') and counts['pending']:
                reasons['paused: new dispatch disabled'] = counts['pending']
            sample = None
            if node['id']=='session' and summary and summary.get('providers'):
                sample = dict(payload_json=json.dumps(summary['providers']))
            if node['id']=='publish' and summary and summary.get('results',{}).get('publish'):
                sample = dict(payload_json=json.dumps(summary['results']['publish']))
            value = dict(id=node['id'] if index is None else f"{node['id']}@{index}", logical_id=node['id'],camera=index,
                         counts=dict(counts),state=state,total=len(selected),held=False,fail_armed=False,reasons=dict(reasons),examples=[dict(w,state=snapshot['states'][w['id']]) for w in selected[:100]],example_total=len(selected),sample=sample,
                         camera_counts=[dict(camera=c, complete=sum(snapshot['states'][w['id']]=='complete' for w in selected if w['camera']==c), total=sum(w['camera']==c for w in selected)) for c in cameras] if node['scope']=='camera_frame' else [],
                         timing=dict(count=timing['calls'],total_ms=1000*timing['seconds'],max_ms=1000*timing['max_seconds'],
                                     span_s=(timing['last_finished_s']-timing['first_started_s']) if timing.get('last_finished_s') is not None else 0))
            if index is None: states.append(value)
            else: partition_states.append(value)
        for index in indices:
            part = dict(node,id=node['id'] if index is None else f"{node['id']}@{index}",logical_id=node['id'],camera=index)
            if index is not None:
                part['label'] += f' · {cameras[index]}'
                part['io_files'] = [node['io_files'][index]] if len(node['io_files'])==len(cameras) else node['io_files']
            partitions.append(part)
        for binding in node['inputs']:
            links = [(d,w['id']) for w in items for port,ids in w['inputs'] if port==binding['port'] for d in ids]
            edge = dict(id=f"{node['id']}:{binding['port']}",source=binding['source'],target=node['id'],
                        port=binding['port'],target_slot=binding['port'],source_slot='out',data_type=binding['data_type'],rule=binding['rule'],
                        inputs_per_item=max(Counter(t for _,t in links).values(),default=0),
                        consumers_per_item=max(Counter(s for s,_ in links).values(),default=0))
            edges.append(edge)
            for source,target in sorted({(partition(by_work[s]),partition(by_work[t])) for s,t in links}):
                partition_edges.append(dict(edge,id=f"{edge['id']}:{source}:{target}",source=source,target=target))
    # Capacity is not part of this snapshot schema; do not invent meter limits.
    resources = {}
    graph = dict(schema_version=3,digest=definition['digest'],synthetic=False,read_only=True,nodes=nodes,partition_nodes=partitions,
                 edges=edges,partition_edges=partition_edges,work_items=len(work),resources=resources,
                 config=dict(task='tracking',frames=definition['frames'],cameras=len(cameras)),contracts={})
    lifetimes = [dict(key=f"{r['node']}/{cameras.index(r['camera']) if r['camera'] is not None else 'all'}",state=r['state'],error=None)
                 for r in snapshot.get('resource_lifetimes',[])]
    run = dict(id='real',graph_digest=definition['digest'],status=snapshot['status'],paused=False,elapsed_s=snapshot['elapsed_s'],
               nodes=states,partition_nodes=partition_states,edges=[],resources=dict(Counter(
                   next(n['resource'] for n in nodes if n['id']==w['node']) for w in work if snapshot['states'][w['id']]=='running')),
               resource_lifetimes=lifetimes,events=[dict(e,node=by_work[e['work']]['node'] if e.get('work') in by_work else '',detail=e.get('detail') or e.get('work','')) for e in snapshot['events']],
               science_complete=snapshot['status']=='complete',artifacts=0,retained_bytes=0,memory_budget=0)
    return dict(graph=graph,run=run)

