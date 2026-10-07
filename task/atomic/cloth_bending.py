"""New mesh bending on consistently wound adjacent cloth faces.

Connected high-bend edges are diagnostic candidates. They do not establish a
unique physical crease, a grasp, settled layering, or self-intersection freedom.
"""
from collections import Counter, defaultdict
import hashlib
import numpy as np


def _state(ids, positions, triangles):
    ids=np.asarray(ids);p=np.asarray(positions,dtype=float);t=np.asarray(triangles)
    if (ids.ndim!=1 or ids.dtype.kind not in 'iu' or len(set(ids.tolist()))!=len(ids)
            or not len(ids) or np.any(ids<0) or p.shape!=(len(ids),3) or not np.isfinite(p).all()
            or t.ndim!=2 or t.shape[1]!=3 or t.dtype.kind not in 'iu' or not len(t)
            or not np.isin(t,ids).all() or np.any(np.diff(np.sort(t,axis=1),axis=1)==0)):
        raise ValueError('cloth bending requires finite positions, distinct persistent IDs and actual integer face topology')
    return ids.astype(np.int64),p,t.astype(np.int64)


class ClothBendingTopology:
    def __init__(self, ids, positions, triangles):
        self.ids,self.initial,self.triangles=_state(ids,positions,triangles)
        self.topology_sha256=hashlib.sha256(np.asarray(self.triangles,dtype='<i8').tobytes()).hexdigest()
        self.lookup={int(i):n for n,i in enumerate(self.ids)}
        self.faces=np.asarray([[self.lookup[int(i)] for i in face] for face in self.triangles])
        incidence=defaultdict(list)
        for n,face in enumerate(self.triangles):
            for a,b in zip(face,np.roll(face,-1)):
                a,b=int(a),int(b);incidence[tuple(sorted((a,b)))].append((n,a<b))
        self.quality=Counter();edges=[];pairs=[]
        for edge,rows in incidence.items():
            if len(rows)==1:self.quality['boundary_edges']+=1
            elif len(rows)!=2:self.quality['nonmanifold_edges']+=1
            elif rows[0][1]==rows[1][1]:self.quality['inconsistent_winding_edges']+=1
            else:edges.append(edge);pairs.append([rows[0][0],rows[1][0]])
        self.edges=np.asarray(edges,dtype=np.int64).reshape(-1,2)
        self.pairs=np.asarray(pairs,dtype=np.int64).reshape(-1,2)
        self.edge_rows=np.asarray([[self.lookup[int(i)] for i in edge] for edge in self.edges],dtype=int).reshape(-1,2)
        self.initial_angles,self.initial_valid=self._angles(self.initial)
        self.initial_lengths=np.linalg.norm(self.initial[self.edge_rows[:,1]]-self.initial[self.edge_rows[:,0]],axis=1)

    def _angles(self, p):
        face=p[self.faces];n=np.cross(face[:,1]-face[:,0],face[:,2]-face[:,0])
        length=np.linalg.norm(n,axis=1);valid=length>1e-14
        n=np.divide(n,length[:,None],out=np.zeros_like(n),where=valid[:,None])
        angle=np.arccos(np.clip(np.einsum('ij,ij->i',n[self.pairs[:,0]],n[self.pairs[:,1]]),-1,1))
        return angle,valid[self.pairs].all(axis=1)

    def measure(self, ids, positions, *, min_bend_rad, min_increase_rad,
                min_component_length_m, max_edge_stretch_fraction=.25):
        values=[min_bend_rad,min_increase_rad,min_component_length_m,max_edge_stretch_fraction]
        if (not np.isfinite(values).all() or min(values)<=0
                or max(min_bend_rad,min_increase_rad)>np.pi):
            raise ValueError('bending thresholds must be positive finite physical values; angles cannot exceed pi')
        ids,p,_=_state(ids,positions,self.triangles)
        if set(ids.tolist())!=set(self.ids.tolist()):raise ValueError('cloth bending particle identity changed')
        lookup={int(i):n for n,i in enumerate(ids)};p=p[[lookup[int(i)] for i in self.ids]]
        angle,valid=self._angles(p);increase=angle-self.initial_angles
        lengths=np.linalg.norm(p[self.edge_rows[:,1]]-p[self.edge_rows[:,0]],axis=1)
        nonzero=self.initial_lengths>1e-10
        stretch=np.divide(lengths-self.initial_lengths,self.initial_lengths,
                          out=np.full_like(lengths,np.inf),where=nonzero)
        usable=valid & self.initial_valid & nonzero & (lengths>1e-10) & (np.abs(stretch)<=max_edge_stretch_fraction)
        selected=usable & (angle>=min_bend_rad) & (increase>=min_increase_rad)
        selected_indices=np.flatnonzero(selected)
        graph=defaultdict(list)
        for i in selected_indices:
            for v in self.edges[i]:graph[int(v)].append(int(i))
        remaining=set(map(int,selected_indices));components=[]
        while remaining:
            frontier=[min(remaining)];indices=set()
            while frontier:
                edge=frontier.pop()
                if edge in indices:continue
                indices.add(edge);remaining.discard(edge)
                for v in self.edges[edge]:frontier.extend(i for i in graph[int(v)] if i not in indices)
            ii=sorted(indices);total=float(lengths[ii].sum())
            degree=Counter(int(v) for edge in self.edges[ii] for v in edge)
            if max(degree.values())>2:shape='branched_network'
            elif all(n==2 for n in degree.values()):shape='closed_loop'
            else:shape='open_chain'
            components.append({'edge_ids':self.edges[ii].tolist(),'total_edge_length_m':total,
                'connectivity':shape,'meets_length_threshold':total>=min_component_length_m,
                'current_bend_rad':angle[ii].tolist(),'initial_bend_rad':self.initial_angles[ii].tolist(),
                'bend_increase_rad':increase[ii].tolist(),'edge_length_m':lengths[ii].tolist(),
                'edge_stretch_fraction':stretch[ii].tolist()})
        components.sort(key=lambda c:(-c['total_edge_length_m'],c['edge_ids']))
        return {'status':'observed_bending_candidates' if any(c['meets_length_threshold'] for c in components)
                         else 'no_candidates_at_declared_thresholds',
            'topology_sha256':self.topology_sha256,'mesh_vertex_count':len(self.ids),'mesh_face_count':len(self.faces),
            'topology_quality':dict(self.quality),'interior_hinges':len(self.edges),
            'usable_hinges':int(usable.sum()),'degenerate_hinges':int((~valid | ~self.initial_valid | ~nonzero).sum()),
            'excluded_stretched_hinges':int((np.abs(stretch)>max_edge_stretch_fraction).sum()),
            'selected_hinges':len(selected_indices),'components':components,
            'thresholds':{'min_bend_rad':min_bend_rad,'min_increase_rad':min_increase_rad,
                          'min_component_length_m':min_component_length_m,'max_edge_stretch_fraction':max_edge_stretch_fraction},
            'scope':'new dihedral bending on adjacent actual material faces; candidates, not certified unique/settled creases or grasp force'}


def capture_cloth_endpoint(session, calibration):
    """Retain full live mesh readback before reset; failures remain explicit."""
    from task.atomic.materials import material_state
    rows={}
    for label,initial in calibration.get('objects',{}).items():
        if str(initial.get('category','')).lower()!='garment':continue
        try:
            state=material_state(session.env,label,'cloth',session.env_idx)
            if state.get('triangles') is None:raise RuntimeError('cloth endpoint has no actual mesh topology')
            recorded=np.asarray(initial['material']['triangles'])
            if not np.array_equal(recorded,state['triangles']):raise RuntimeError('cloth endpoint topology differs from initial readback')
            if set(initial['material']['ids'])!=set(state['ids'].tolist()):raise RuntimeError('cloth endpoint persistent population differs')
            rows[label]={'status':'captured','ids':state['ids'].tolist(),'positions_world':state['positions'].tolist(),
                'topology_sha256':state['topology_sha256'],'source':state['source'],
                'coordinate_frame':'environment_local_world','length_unit':'metres',
                'physics_step':getattr(getattr(session.env,'_atomic_contacts',None),'steps',None),
                'policy_action_index':session._action_index()}
        except (KeyError,ValueError,RuntimeError,AttributeError) as error:
            rows[label]={'status':'capture_failed','reason':str(error)}
    return {'status':'captured' if rows and all(r['status']=='captured' for r in rows.values())
                     else 'capture_failed' if rows else 'no_initial_garment_readback',
            'garments':rows,'scope':'full endpoint mesh diagnostic; no new action-success or geometric conditioning gate'}


class ClothEndpointHistory:
    """Bounded synchronized full meshes for endpoint persistence diagnostics."""
    def __init__(self, calibration, stride=4, capacity=8):
        self.calibration = calibration
        self.stride, self.capacity = stride, capacity
        self.samples = []
        self.last_step = None

    def observe(self, session, force=False):
        step = getattr(getattr(session.env, '_atomic_contacts', None), 'steps', None)
        if step is None or step == self.last_step:
            return
        if not force and self.last_step is not None and 0 < step-self.last_step < self.stride:
            return
        sample = capture_cloth_endpoint(session, self.calibration)
        sample.update(physics_step=step, dt_s=getattr(session.env, 'dt', None))
        self.samples.append(sample)
        del self.samples[:-self.capacity]
        self.last_step = step

    def summary(self):
        from copy import deepcopy
        return {'sampling_stride_steps': self.stride, 'capacity': self.capacity,
                'samples': deepcopy(self.samples),
                'scope': 'sampled endpoint persistence; does not certify intermediate motion between samples'}


def measure_bending_persistence(topology, endpoint, history, label, *,
        min_duration_s=.1, max_vertex_drift_m=.002, max_bend_change_rad=np.pi/90):
    """Check retained candidates over a synchronized, bounded endpoint window.

    These are stable bending candidates, not a crease-to-task-role binding or
    a self-intersection/cloth-grasp certificate.
    """
    thresholds = [min_duration_s, max_vertex_drift_m, max_bend_change_rad]
    if not np.isfinite(thresholds).all() or min(thresholds) <= 0:
        raise ValueError('persistence bounds must be finite positive physical values')
    result = {'status': 'unavailable_temporal_witness', 'components': [],
        'thresholds': {'min_duration_s': min_duration_s, 'max_vertex_drift_m': max_vertex_drift_m,
                       'max_bend_change_rad': max_bend_change_rad},
        'scope': 'sampled stable new bending; not a certified unique physical crease, layering or grasp'}
    if not history:
        result['reason'] = 'no_full_mesh_history'
        return result
    try:
        samples = history['samples']; stride = history['sampling_stride_steps']
        if type(stride) is not int or stride < 1 or len(samples) < 2:
            raise ValueError('insufficient synchronized mesh samples')
        steps = [s['physics_step'] for s in samples]
        if any(type(s) is not int for s in steps) or any(not 0 < b-a <= stride for a,b in zip(steps,steps[1:])):
            raise ValueError('mesh history has duplicated, reversed or missing sample intervals')
        dt = [s['dt_s'] for s in samples]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v <= 0 for v in dt) or len(set(dt)) != 1:
            raise ValueError('mesh history requires a constant finite positive simulation dt')
        duration = (steps[-1]-steps[0])*dt[0]
        result.update(sample_count=len(samples), duration_s=duration, first_physics_step=steps[0], last_physics_step=steps[-1])
        if duration < min_duration_s:
            result['reason'] = 'mesh_history_duration_below_threshold'
            return result
        positions = []; measured = []
        for sample in samples:
            row = sample['garments'][label]
            if (row['status'] != 'captured' or row['physics_step'] != sample['physics_step']
                    or row['topology_sha256'] != topology.topology_sha256
                    or row['coordinate_frame'] != 'environment_local_world' or row['length_unit'] != 'metres'):
                raise ValueError('mesh history frame, time or topology witness is inconsistent')
            ids,p,_ = _state(row['ids'], row['positions_world'], topology.triangles)
            if set(ids.tolist()) != set(topology.ids.tolist()):
                raise ValueError('mesh history persistent particle population changed')
            lookup = {int(v):i for i,v in enumerate(ids)}
            positions.append(p[[lookup[int(v)] for v in topology.ids]])
            measured.append(topology.measure(ids,p,**endpoint['thresholds']))
        if not np.array_equal(positions[-1], np.asarray(endpoint['endpoint_positions'])):
            raise ValueError('mesh history does not end at the scored endpoint')
        edge_lookup = {tuple(map(int,edge)):i for i,edge in enumerate(topology.edges)}
        angles = [topology._angles(p)[0] for p in positions]
        positions = np.asarray(positions)
        for candidate in endpoint['components']:
            if not candidate['meets_length_threshold']:
                continue
            edges = {tuple(e) for e in candidate['edge_ids']}
            vertex_rows = [topology.lookup[v] for v in sorted({v for e in edges for v in e})]
            ii = [edge_lookup[e] for e in sorted(edges)]
            # Pairwise diameter catches out-and-back drift as well as accumulated motion.
            drift = max(float(np.linalg.norm(a[vertex_rows]-b[vertex_rows],axis=1).max())
                        for a in positions for b in positions)
            bend_change = float(np.ptp(np.asarray(angles)[:,ii],axis=0).max())
            persistent = all(edges <= {tuple(e) for c in m['components'] for e in c['edge_ids']}
                             for m in measured)
            accepted = persistent and drift <= max_vertex_drift_m and bend_change <= max_bend_change_rad
            result['components'].append({'edge_ids':candidate['edge_ids'],
                'connectivity':candidate['connectivity'], 'total_edge_length_m':candidate['total_edge_length_m'],
                'persistent_new_bending':persistent, 'max_vertex_drift_m':drift,
                'max_bend_change_rad':bend_change, 'within_sampled_stability_bounds':accepted})
        result['stable_candidate_count'] = sum(c['within_sampled_stability_bounds'] for c in result['components'])
        result['status'] = 'observed_sampled_stable_bending' if result['stable_candidate_count'] else 'no_sampled_stable_candidates'
    except (KeyError,ValueError,TypeError,IndexError) as error:
        result.update(status='invalid_temporal_witness', reason=str(error))
    return result
