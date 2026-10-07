"""Recompute retained named-support force signs independently of score flags."""
import numpy as np


def validate_support_witness(measured):
    evidence = measured.get('support_contact_evidence')
    scope = 'retained named-body force signs; not weight balance or intermediate contact lifecycle'
    if not isinstance(evidence, dict):
        return {'status': 'partial_support_evidence', 'unavailable': ['raw_support_contacts'], 'scope': scope}
    failed = []
    try:
        rows = evidence['contacts']
        if not isinstance(rows, list): raise ValueError('contact list')
        axis = np.asarray(evidence['normal_axis_world'], dtype=float)
        if axis.shape != (3,) or not np.isfinite(axis).all() or not np.isclose(np.linalg.norm(axis), 1):
            raise ValueError('support axis')
        thresholds = evidence.get('support_eligibility')
        # Legacy records used the fixed normal cone, but did not retain it.
        normal_min, impulse_min = ((thresholds['min_normal_axis_dot'], thresholds['min_axial_impulse_ns'])
                                   if thresholds is not None else (.5, 1e-9))
        if normal_min not in (1e-6, .5) or impulse_min != 1e-9:
            raise ValueError('unknown support thresholds')
        object_path = evidence.get('object_contact_scope', evidence['object_root'])
        supports = evidence.get('support_contact_scopes', evidence['support_roots'])
        def matches(row, index, path):
            return isinstance(path, str) and any(p == path or p.startswith(path + '/')
                for p in (row[f'actor{index}'], row[f'collider{index}']))
        for row in rows:
            support_path = supports[row['support_label']]
            indices = [i for i in (0, 1) if matches(row, i, object_path) and matches(row, 1-i, support_path)]
            if len(indices) != 1:
                failed.append('named_body_identity'); continue
            sign = 1 if indices[0] == 0 else -1
            normal = np.asarray(row['normal_world'], dtype=float) * sign
            impulse = np.asarray(row['impulse'], dtype=float) * sign
            if (normal.shape != (3,) or impulse.shape != (3,)
                    or not np.isfinite(normal).all() or not np.isfinite(impulse).all()):
                failed.append('finite_force_vectors'); continue
            if float(normal @ axis) <= normal_min: failed.append('upward_normal')
            if float(impulse @ axis) <= impulse_min: failed.append('upward_impulse')
            for key, value in [('normal_on_object_world', normal), ('impulse_on_object_world', impulse)]:
                if key in row and not np.allclose(row[key], value, rtol=1e-7, atol=1e-12):
                    failed.append('oriented_force_vector')
            for key, value in [('normal_axis_dot', float(normal @ axis)), ('axial_impulse_ns', float(impulse @ axis))]:
                if key in row and not np.isclose(row[key], value, rtol=1e-7, atol=1e-12):
                    failed.append('force_projection')
        if bool(rows) != measured.get('support_contact'): failed.append('support_flag')
        unavailable = [] if thresholds is not None else ['recorded_support_thresholds']
        if evidence.get('support_evidence_kind') == 'persistent_unchanged_contact':
            unavailable.append('intermediate_lifecycle_and_unchanged_pose_history')
    except (KeyError, ValueError, TypeError, IndexError) as error:
        failed.append('malformed_support_evidence'); unavailable = []
    return {'status': 'inconsistent_support_evidence' if failed else
            'partial_support_evidence' if unavailable else 'consistent_support_evidence',
            'failed_checks': sorted(set(failed)), 'unavailable': unavailable, 'scope': scope}
