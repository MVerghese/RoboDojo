"""Validated, JSON-serializable definitions of atomic RoboDojo trials."""

from dataclasses import dataclass
from copy import deepcopy
import json
import math
from pathlib import Path


FAMILIES = frozenset(
    {
        "pick", "place", "push", "push_with_tool", "pour", "actuate",
        "twist", "insert", "touch_with_tool", "handover", "fold",
    }
)
GEOMETRY_KINDS = frozenset(
    {"point", "pose", "relative_displacement", "relative_orientation", "spatial_relation"}
)
EVENT_KINDS = frozenset({"stage_success", "first_lift", "first_motion", "first_predicate", "first_contact", "before_contact", "recognition_event", "attempt_end"})
CONTACT_KINDS = frozenset({'contact_points', 'object_contact_points'})
MEASUREMENT_KINDS = frozenset({"object_pose", "object_position", "object_center_pose", "object_center_position", "robot_ee_pose", "functional_point", "support_point", "articulated_link_pose", "joint_link_pose"}) | CONTACT_KINDS
MEASUREMENT_KINDS |= {'cloth_points','cloth_landmark','cloth_patch_frame','cloth_patch_surface','cloth_model_patch','cloth_tag_frame','cloth_line_frame','fluid_points','calibrated_frame'}
FRAME_KINDS = MEASUREMENT_KINDS - {'object_position', 'object_center_position','cloth_points','cloth_landmark','fluid_points'} - CONTACT_KINDS
OBJECT_FRAME_KINDS = {'object_pose', 'object_center_pose','articulated_link_pose','joint_link_pose','calibrated_frame','cloth_patch_surface','cloth_model_patch'}
SPATIAL_RELATIONS = frozenset({'above', 'below', 'left_of', 'right_of', 'in_front_of', 'behind',
                               'near', 'inside_box', 'inside_region', 'inside_aperture', 'on_top','layered_over','intersects_segment','coincides_with_segment'})


def _finite_number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric data')
    if value < 0 or (positive and value == 0):
        raise ValueError(f'{name} must be {"positive" if positive else "nonnegative"}')


def _geometry_vector(value, size, name, quaternion=False):
    if not isinstance(value, (list, tuple)) or len(value) != size or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError(f'{name} must be a finite {size}-vector')
    if quaternion and math.hypot(*value) == 0:
        raise ValueError(f'{name} quaternion must be nonzero')


def _geometry_axes(value, name):
    if not isinstance(value, list) or not value or any(type(x) is not int or x not in (0, 1, 2) for x in value) or len(set(value)) != len(value):
        raise ValueError(f'{name} must be a nonempty, unique subset of [0,1,2]')


def _read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _validate_selector(selector, name):
    if not isinstance(selector, dict) or selector.get("kind") not in MEASUREMENT_KINDS:
        raise ValueError(f"{name} must have kind in {sorted(MEASUREMENT_KINDS)}")
    common = {'kind', 'time'}
    fields = {'robot_ee_pose': {'arm', 'label', 'min_finger_bodies'},
              'calibrated_frame': {'label', 'local_pose', 'calibration_id', 'asset_uuid','asset_model'},
              'object_pose': {'label', 'mesh_paths', 'calibration_id', 'asset_uuid','asset_model'},
              'functional_point': {'label', 'tag', 'type', 'index'},
              'support_point': {'label', 'tag', 'type', 'index'},
              'contact_points': {'label', 'arm', 'min_finger_bodies', 'joint_tag'},
              'articulated_link_pose': {'label', 'link'},
              'joint_link_pose': {'label', 'joint_tag'},
              'cloth_points': {'label','ids'}, 'cloth_landmark': {'label','tag'},
              'cloth_tag_frame': {'label','tag'},
              'cloth_line_frame': {'label','tag_a','tag_b','normal_tag'},
              'cloth_patch_surface': {'label','origin_id','x_id','y_id','face_ids'},
              'cloth_model_patch': {'label','models'},
              'cloth_patch_frame': {'label','origin_id','x_id','y_id'}, 'fluid_points': {'label','ids'},
              'object_contact_points': {'label', 'other_label'}}.get(selector['kind'], {'label'})
    if set(selector) - common - fields:
        raise ValueError(f'{name} has unsupported selector fields: {set(selector) - common - fields}')
    if selector.get('time', 'live') not in ('live', 'stage_start'):
        raise ValueError(f'{name}.time must be live or stage_start')
    if selector.get('time') == 'stage_start' and selector['kind'] not in FRAME_KINDS:
        raise ValueError('a frozen reference requires an actual landmark frame')
    if selector["kind"] == "robot_ee_pose":
        if not selector.get("arm"):
            raise ValueError(f"{name}.arm is required for robot_ee_pose")
        if selector["arm"] in ('nearest', 'contacting') and not selector.get("label"):
            raise ValueError(f"{name}.label is required when arm is nearest/contacting")
        if 'min_finger_bodies' in selector:
            if selector['arm'] != 'contacting' or type(selector['min_finger_bodies']) is not int or selector['min_finger_bodies'] < 1:
                raise ValueError('robot frame finger count applies only to a physically contacting arm')
    elif not selector.get("label"):
        raise ValueError(f"{name}.label is required for {selector['kind']}")
    if selector['kind'] == 'calibrated_frame':
        _geometry_vector(selector.get('local_pose'),7,'calibrated_frame.local_pose')
        if math.hypot(*selector['local_pose'][3:]) == 0:
            raise ValueError('calibrated frame orientation must be nonzero')
        if not isinstance(selector.get('calibration_id'),str) or not selector['calibration_id']:
            raise ValueError('calibrated frame needs reviewed calibration provenance')
    if 'asset_uuid' in selector and (not isinstance(selector['asset_uuid'],str) or not selector['asset_uuid']):
        raise ValueError('calibrated asset identity must be a nonempty UUID')
    if 'asset_model' in selector:
        model=selector['asset_model']
        if (not isinstance(model,dict) or set(model)!={'name','index'} or not isinstance(model['name'],str)
                or not model['name'] or type(model['index']) is not int or model['index']<0):
            raise ValueError('calibrated asset_model requires a model name and nonnegative integer index')
    if 'mesh_paths' in selector:
        paths=selector['mesh_paths']
        if (not isinstance(paths,list) or not paths or len(set(paths))!=len(paths)
                or any(not isinstance(p,str) or not p or p.startswith('/') or any(s in ('','.','..') for s in p.split('/')) for p in paths)):
            raise ValueError('mesh_paths requires distinct root-relative prim paths inside the selected object')
        if not selector.get('calibration_id'):
            raise ValueError('selected material meshes require calibration provenance')
    if selector['kind'] in ('functional_point', 'support_point'):
        if not selector.get('tag') or selector.get('type', 'active') not in ('active', 'passive'):
            raise ValueError('functional_point requires a tag and active/passive type')
        if type(selector.get('index', 0)) is not int or selector.get('index', 0) < 0:
            raise ValueError('functional_point index must be nonnegative')
    if selector['kind'] == 'contact_points':
        if not isinstance(selector.get('arm', 'any'), str) or not selector.get('arm', 'any'):
            raise ValueError('contact arm must be a nonempty name or any')
        count = selector.get('min_finger_bodies', 1)
        if type(count) is not int or count < 1:
            raise ValueError('min_finger_bodies must be a positive integer')
    for field in ('joint_tag', 'link'):
        if field in fields and (selector['kind'] != 'contact_points' or field in selector):
            if not isinstance(selector.get(field), str) or not selector[field]:
                raise ValueError(f'{name}.{field} must name an actual link or annotated joint tag')
    if selector['kind'] == 'object_contact_points':
        if not isinstance(selector.get('other_label'), str) or not selector['other_label']:
            raise ValueError('object_contact_points requires the other object label')
        if selector['other_label'] == selector['label']:
            raise ValueError('object contact requires two distinct labels')
    if selector['kind'] in ('cloth_points','fluid_points'):
        ids=selector.get('ids')
        if not isinstance(ids,list) or not ids or any(type(i) is not int or i<0 for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('material points require distinct explicit nonnegative IDs')
    if selector['kind'] in ('cloth_landmark','cloth_tag_frame') and (not isinstance(selector.get('tag'),str) or not selector['tag']):
        raise ValueError('cloth landmark requires an annotated material tag')
    if selector['kind']=='cloth_line_frame':
        if any(not isinstance(selector.get(k),str) or not selector[k] for k in ('tag_a','tag_b','normal_tag')) or selector['tag_a']==selector['tag_b']:
            raise ValueError('cloth crease needs two distinct material tags and a real normal tag')
    if selector['kind'] in ('cloth_patch_frame','cloth_patch_surface'):
        ids=[selector.get(k) for k in ('origin_id','x_id','y_id')]
        if any(type(i) is not int or i<0 for i in ids) or len(set(ids))!=3:
            raise ValueError('cloth patch frame requires three distinct material vertex IDs')
    if selector['kind']=='cloth_patch_surface':
        ids=selector.get('face_ids')
        if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids) or any(type(i) is not int or i<0 for i in ids):
            raise ValueError('cloth patch surface requires distinct explicit persistent topology face IDs')
    if selector['kind']=='cloth_model_patch':
        import re
        models=selector.get('models')
        if not isinstance(models,dict) or not models:raise ValueError('cloth model patch requires reviewed model alternatives')
        for model,row in models.items():
            if not isinstance(model,str) or not re.fullmatch(r'[^/]+/[0-9]{5}',model):
                raise ValueError('cloth patch alternatives require model-name/5-digit-index keys')
            if not isinstance(row,dict) or set(row)!={'face_ids','origin_id','x_id','y_id','asset_sha256','topology_sha256'}:
                raise ValueError('cloth model patch requires explicit faces/frame and asset/topology hashes')
            if any(not isinstance(row[k],str) or not re.fullmatch('[a-f0-9]{64}',row[k]) for k in ('asset_sha256','topology_sha256')):
                raise ValueError('cloth model patch hashes must be SHA256 hex')
            _validate_selector({'kind':'cloth_patch_surface','label':selector['label'],
                **{k:row[k] for k in ('face_ids','origin_id','x_id','y_id')}},name+'.'+model)


def _validate_condition(condition):
    if not isinstance(condition, dict) or not condition.get("id") or not condition.get("slot"):
        raise ValueError("each geometry condition needs id and slot")
    if condition.get("kind") not in GEOMETRY_KINDS:
        raise ValueError(f"unsupported geometry kind: {condition.get('kind')}")
    if "expected" not in condition or "tolerance" not in condition:
        raise ValueError(f"condition {condition['id']} needs expected and tolerance")
    kind = condition['kind']
    _finite_number(condition['tolerance'], 'tolerance')
    if kind in ('point', 'relative_displacement'):
        _geometry_vector(condition['expected'], 3, 'expected')
    elif kind == 'pose':
        expected = condition['expected']
        if not isinstance(expected, dict) or not {'position', 'orientation'}.issubset(expected):
            raise ValueError('pose expected needs position and orientation')
        _geometry_vector(expected['position'], 3, 'expected.position')
        _geometry_vector(expected['orientation'], 4, 'expected.orientation', quaternion=True)
        if 'angle_tolerance_rad' not in condition:
            raise ValueError('pose needs an explicit angle_tolerance_rad separate from position tolerance')
    elif kind == 'relative_orientation':
        _geometry_vector(condition['expected'], 4, 'expected', quaternion=True)
    elif not isinstance(condition['expected'], str) or condition['expected'] not in SPATIAL_RELATIONS:
        raise ValueError('unsupported spatial relation; add a measured relation adapter first')
    if 'axes' in condition:
        if kind not in ('point', 'relative_displacement'):
            raise ValueError('axes only applies to point/displacement; other checkers would ignore it')
        _geometry_axes(condition['axes'], 'axes')
    if 'orientation_axes' in condition:
        if kind != 'relative_orientation':
            raise ValueError('orientation_axes only applies to relative_orientation')
        _geometry_axes(condition['orientation_axes'], 'orientation_axes')
    if 'angle_tolerance_rad' in condition:
        if kind != 'pose':
            raise ValueError('angle_tolerance_rad only applies to pose')
        _finite_number(condition['angle_tolerance_rad'], 'angle_tolerance_rad')
    for field in ('relation_scope', 'margin', 'half_extents', 'min_overlap_fraction', 'interior_boxes', 'aperture_profile', 'required_clearance_m','min_layer_gap_m','max_layer_gap_m'):
        if field in condition and kind != 'spatial_relation':
            raise ValueError(f'{field} only applies to spatial_relation')
    _validate_selector(condition.get("measurement"), f"condition {condition['id']}.measurement")
    measurement = condition['measurement']
    if measurement.get('time', 'live') != 'live':
        raise ValueError('measurements must be live; stage_start is a reference snapshot, not a referent-selection adapter')
    if kind in ('pose', 'relative_orientation') and measurement['kind'] not in FRAME_KINDS:
        raise ValueError('orientation requires an actual frame selector, not a point')
    if measurement['kind'] == 'contact_points' and condition['kind'] in ('pose', 'relative_orientation'):
        raise ValueError('contact points have no orientation; name a real orientation landmark separately')
    if condition['slot'] in ('grasp_region', 'contact') and measurement['kind'] == 'robot_ee_pose':
        if not condition.get('legacy_ee_proxy', False):
            raise ValueError('grasp/contact position must use actual contact_points, not an end-effector origin')
    if condition['kind'] == 'spatial_relation' and measurement['kind'] in OBJECT_FRAME_KINDS:
        if condition.get('relation_scope') != 'objects':
            raise ValueError('object spatial relations must explicitly use geometry-aware objects scope')
        if condition.get('expected') == 'near':
            raise ValueError('object surface near is not implemented; centre distance is not accepted')
    if kind == 'spatial_relation' and measurement['kind'] in ('object_position', 'object_center_position'):
        if condition.get('relation_scope') != 'points':
            raise ValueError('object position relations require explicit points scope; they do not measure whole objects')
    if condition.get("reference") is not None:
        _validate_selector(condition["reference"], f"condition {condition['id']}.reference")
        if condition['reference']['kind'] not in FRAME_KINDS:
            raise ValueError('reference must identify an oriented landmark frame')
    elif kind in ('relative_displacement', 'relative_orientation', 'spatial_relation'):
        raise ValueError('relative geometry needs an explicit reference landmark frame')
    if kind == 'spatial_relation':
        scope = condition.get('relation_scope', 'points')
        if scope not in ('points', 'objects','segments'):
            raise ValueError('relation_scope must be points, objects or segments')
        if scope == 'objects' and (measurement['kind'] not in OBJECT_FRAME_KINDS or
                                   (condition['reference']['kind'] not in OBJECT_FRAME_KINDS and condition['expected'] != 'inside_aperture')):
            raise ValueError('objects scope needs object frame selectors; it cannot replace functional landmarks')
        relation = condition['expected']
        if scope=='segments' or relation in ('intersects_segment','coincides_with_segment'):
            if scope!='segments' or relation not in ('intersects_segment','coincides_with_segment') or any(c['kind']!='cloth_line_frame' for c in (measurement,condition['reference'])):
                raise ValueError('finite segment relations require actual cloth_line_frame endpoints and segments scope')
        if relation == 'layered_over':
            if scope!='objects' or measurement['kind'] not in ('cloth_patch_surface','cloth_model_patch') or condition['reference']['kind'] not in ('cloth_patch_surface','cloth_model_patch') or condition['reference'].get('time')=='stage_start':
                raise ValueError('layered_over requires two live actual material patch surfaces')
            for field in ('min_layer_gap_m','max_layer_gap_m'):_finite_number(condition.get(field),field)
            if condition['min_layer_gap_m']>condition['max_layer_gap_m']:
                raise ValueError('layer gap bounds are reversed')
        elif 'min_layer_gap_m' in condition or 'max_layer_gap_m' in condition:
            raise ValueError('layer gap bounds apply only to layered_over')
        if relation == 'on_top' and condition['reference'].get('time') == 'stage_start':
            raise ValueError('supported-on requires a live support frame and contact, not historical geometry')
        if 'margin' in condition and relation in ('near', 'inside_box', 'inside_region', 'inside_aperture', 'on_top','layered_over','intersects_segment','coincides_with_segment'):
            raise ValueError('margin only applies to directional separation relations')
        if 'half_extents' in condition and not (relation == 'inside_box' or (scope == 'points' and relation == 'on_top')):
            raise ValueError('half_extents requires a box relation')
        _finite_number(condition.get('margin', 0), 'margin')
        if relation == 'inside_region':
            if scope != 'objects':
                raise ValueError('inside_region certifies a whole solid object, not a centre point')
            from task.atomic.regions import validate_boxes
            validate_boxes(condition.get('interior_boxes'))
        elif 'interior_boxes' in condition:
            raise ValueError('interior_boxes only applies to inside_region')
        if relation == 'inside_aperture':
            if scope != 'objects' or condition['reference'].get('time') == 'stage_start':
                raise ValueError('inside_aperture requires a whole object and a live calibrated opening frame')
            from task.atomic.fit import aperture_polygon
            aperture_polygon(condition.get('aperture_profile'))
            _finite_number(condition.get('required_clearance_m', 0.), 'required_clearance_m')
        elif 'aperture_profile' in condition or 'required_clearance_m' in condition:
            raise ValueError('aperture profile and clearance only apply to inside_aperture')
        if condition['expected'] in ('inside_box', 'on_top'):
            if condition['expected'] == 'inside_box' or scope == 'points':
                _geometry_vector(condition.get('half_extents'), 3, 'half_extents')
                if any(x <= 0 for x in condition['half_extents']):
                    raise ValueError('half_extents must be positive')
        if 'min_overlap_fraction' in condition:
            if scope != 'objects' or relation in ('inside_box', 'inside_region', 'inside_aperture'):
                raise ValueError('min_overlap_fraction only applies to projected object relations')
            _finite_number(condition['min_overlap_fraction'], 'min_overlap_fraction', positive=True)
            if condition['min_overlap_fraction'] > 1:
                raise ValueError('min_overlap_fraction must be in (0,1]')
    event = condition.get("event", {"kind": "stage_success"})
    _validate_event(event)
    if event['kind'] == 'before_contact' and measurement['kind'] in CONTACT_KINDS:
        raise ValueError('before_contact needs an independently measurable approach point/frame, not a nonexistent contact')
    if event['kind'] == 'attempt_end' and measurement['kind'] in CONTACT_KINDS:
        raise ValueError('attempt_end measures final state, not a past interaction contact')


def _validate_event(event):
    if not isinstance(event, dict) or event.get("kind") not in EVENT_KINDS:
        raise ValueError('unsupported geometric sampling event')
    if event["kind"] in ("first_lift", "first_motion") and not event.get("label"):
        raise ValueError('sampling event needs object label')
    if event['kind'] in ('first_lift', 'first_motion'):
        _finite_number(event.get('threshold', 0.01), 'event threshold', positive=True)
    if event["kind"] == "first_predicate":
        checks = event.get("checks")
        if not isinstance(checks, list) or not checks or event.get("mode", "any") not in ("any", "all"):
            raise ValueError('first_predicate needs checks and any/all mode')
        for check in checks:
            _validate_check(check)
    if event['kind'] in ('first_contact', 'before_contact'):
        _validate_selector(event.get('measurement'), 'first_contact.measurement')
        if event['measurement']['kind'] not in CONTACT_KINDS:
            raise ValueError('first_contact requires physical contact measurement')
        if event['measurement'].get('time', 'live') != 'live':
            raise ValueError('first_contact requires live contacts')
    if event['kind'] == 'recognition_event' and not isinstance(event.get('name'), str):
        raise ValueError('recognition_event requires a named physical transition')


def _validate_check(check):
    if not isinstance(check, dict) or not isinstance(check.get("name"), str) or not isinstance(check.get("args"), dict):
        raise ValueError("success_checks entries need name and args")
    if not check["name"].startswith("is_"):
        raise ValueError("atomic success checks must be read-only is_* predicates")
    if check["args"].get("update"):
        raise ValueError("atomic success checks must not update parser state")
    if check['name'] == 'is_atomic_rise_since_activation':
        args = check['args']
        if set(args) != {'label', 'threshold_m'} or not isinstance(args['label'], str) or not args['label']:
            raise ValueError('private rise check needs label and threshold_m')
        _finite_number(args['threshold_m'], 'rise threshold', positive=True)
    if check['name'] in ('is_joint_position_ratio_change_from_above_to_below', 'is_joint_position_change',
                         'is_functional_point_moved', 'is_functional_point_not_moved'):
        raise ValueError('stateful native predicates are forbidden in observers; use a private physical recognizer')


def _validate_recognition(recognition, family):
    if recognition is None:
        if family in ('pick', 'push'):
            raise ValueError(f'{family} requires explicit recognition independent of geometry')
        return
    if isinstance(recognition, dict) and recognition.get('kind') != 'finger_contact_motion':
        from task.atomic.recognizers import validate_recognition
        validate_recognition(recognition, family, _validate_selector)
        return
    allowed = {'kind', 'label', 'arm', 'motion_threshold_m', 'min_contact_steps'}
    if family == 'push':
        allowed.add('support_labels')
    if not isinstance(recognition, dict) or set(recognition) != allowed:
        raise ValueError(f'{family} recognition needs exactly {sorted(allowed)}')
    if family not in ('pick', 'push') or recognition['kind'] != 'finger_contact_motion':
        raise ValueError('only pick/push finger_contact_motion recognition is implemented')
    if not isinstance(recognition['label'], str) or not recognition['label']:
        raise ValueError('recognition needs an object label')
    if not isinstance(recognition['arm'], str) or not recognition['arm']:
        raise ValueError('recognition arm must be a nonempty name or any')
    _finite_number(recognition['motion_threshold_m'], 'recognition motion threshold', positive=True)
    if type(recognition['min_contact_steps']) is not int or recognition['min_contact_steps'] < 2:
        raise ValueError('recognition needs at least two distinct consecutive contact physics steps')
    if family == 'push':
        supports = recognition['support_labels']
        if (not isinstance(supports, list) or not supports
                or any(not isinstance(s, str) or not s for s in supports)
                or len(supports) != len(set(supports)) or recognition['label'] in supports):
            raise ValueError('push recognition needs distinct named support_labels; @table names the scene table')


def _validate_stage_event(condition, recognition):
    event = condition.get('event', {})
    if event.get('kind') == 'recognition_event':
        from task.atomic.recognizers import TRANSITIONS
        if not recognition or event['name'] not in TRANSITIONS.get(recognition['kind'], ()):
            raise ValueError('recognition_event must name a transition emitted by this stage recognizer')


@dataclass(frozen=True)
class AtomicStage:
    id: str
    family: str
    instruction: str
    success_checks: tuple[dict, ...]
    geometry: tuple[dict, ...]
    step_limit: int | None = None
    recognition: dict | None = None
    maintained_holds: tuple[dict, ...] = ()
    trajectories: tuple[dict, ...] = ()
    selection: dict | None = None
    required: bool = True

    @classmethod
    def from_dict(cls, data):
        if not data.get("id") or data.get("family") not in FAMILIES or not data.get("instruction"):
            raise ValueError("stage needs id, valid family, and instruction")
        checks = tuple(data.get("success_checks", ()))
        if not checks:
            raise ValueError(f"stage {data['id']} needs at least one success check")
        for check in checks:
            _validate_check(check)
        recognition = deepcopy(data.get('recognition'))
        _validate_recognition(recognition, data['family'])
        if recognition is not None and data['family'] == 'pick':
            for check in checks:
                if check['name'] == 'is_lift' and check['args'].get('label', recognition['label']) != recognition['label']:
                    raise ValueError('pick lift goal and physical recognition must name the same object')
                if check['name'] == 'is_lift':
                    _finite_number(check['args'].get('z_threshold'), 'pick lift threshold', positive=True)
        geometry = tuple(data.get("geometry", ()))
        for condition in geometry:
            _validate_condition(condition)
            _validate_stage_event(condition, recognition)
        ids = [condition["id"] for condition in geometry]
        if len(ids) != len(set(ids)):
            raise ValueError(f"stage {data['id']} has duplicate condition ids")
        step_limit = data.get("step_limit")
        if step_limit is not None and (not isinstance(step_limit, int) or step_limit <= 0):
            raise ValueError("step_limit must be a positive integer")
        maintained_holds = tuple(deepcopy(data.get('maintained_holds', ())))
        for hold in maintained_holds:
            _validate_selector({'kind': 'contact_points', **hold}, 'maintained_holds')
            if set(hold) != {'label', 'arm', 'min_finger_bodies'} or hold['min_finger_bodies'] < 2:
                raise ValueError('maintained_holds requires label, arm and at least two distinct fingers')
        trajectories = tuple(deepcopy(data.get('trajectories', ())))
        from task.atomic.trajectory import validate_trajectory
        for trajectory in trajectories:
            validate_trajectory(trajectory, _validate_selector, _validate_event)
            _validate_stage_event({'event':trajectory['start_event']}, recognition)
            _validate_stage_event({'event':trajectory['end_event']}, recognition)
        if len({t['id'] for t in trajectories}) != len(trajectories):
            raise ValueError('trajectory IDs must be unique')
        selection = deepcopy(data.get('selection'))
        if selection is not None:
            from task.atomic.selection import validate_selection
            validate_selection(selection, _validate_condition)
        if type(data.get('required', True)) is not bool:
            raise ValueError('required must be boolean')
        return cls(data["id"], data["family"], data["instruction"], checks, geometry, step_limit, recognition, maintained_holds, trajectories, selection, data.get('required', True))

    def with_variant(self, variant):
        """Overlay instruction and expected geometry without changing the task.

        A variant may update expected values, tolerances, landmarks, or events
        by condition id. It cannot silently add a new success predicate.
        """
        if variant.get("stage_id") != self.id:
            raise ValueError("variant stage_id does not match selected stage")
        overrides = variant.get("conditions", {})
        if set(overrides) - {c["id"] for c in self.geometry}:
            raise ValueError("variant refers to unknown geometry condition")
        conditions = []
        for condition in self.geometry:
            changed = {**condition, **overrides.get(condition["id"], {})}
            if changed["id"] != condition["id"] or changed["slot"] != condition["slot"]:
                raise ValueError("variant cannot change condition identity or slot")
            _validate_condition(changed)
            _validate_stage_event(changed, self.recognition)
            conditions.append(changed)
        return AtomicStage(
            self.id, self.family, variant.get("instruction", self.instruction),
            self.success_checks, tuple(conditions), self.step_limit, deepcopy(self.recognition), deepcopy(self.maintained_holds),
            deepcopy(self.trajectories), deepcopy(self.selection), self.required,
        )


@dataclass(frozen=True)
class AtomicProgram:
    task_name: str
    stages: tuple[AtomicStage, ...]
    instruction: str | None = None
    geometric_instruction: str | None = None
    stage_dependencies: dict | None = None
    repeat_counts: dict | None = None
    gates: tuple = ()
    binding_evidence: dict | None = None
    choices: tuple = ()
    label_templates: dict | None = None

    def __post_init__(self):
        stage_ids = {s.id for s in self.stages}
        if not self.stages or len(stage_ids) != len(self.stages):
            raise ValueError('atomic program needs unique, nonempty stages')
        gate_ids = {g.id for g in self.gates}
        if len(gate_ids) != len(self.gates) or stage_ids & gate_ids:
            raise ValueError('gates require unique IDs distinct from action stages')
        choice_ids = {c.id for c in self.choices}
        if len(choice_ids)!=len(self.choices) or choice_ids & (stage_ids|gate_ids):
            raise ValueError('choices require unique IDs distinct from gates and stages')
        if self.label_templates is not None:
            fields = {'prefix', 'placeholder', 'min', 'max', 'category'}
            if not isinstance(self.label_templates, dict) or not self.label_templates or set(self.label_templates) - stage_ids:
                raise ValueError('label_templates must name existing stage templates')
            for ident, binding in self.label_templates.items():
                if (not isinstance(binding, dict) or set(binding) != fields
                        or not isinstance(binding['prefix'], str) or not binding['prefix']
                        or not isinstance(binding['placeholder'], str) or not binding['placeholder'].startswith('$') or len(binding['placeholder']) < 2
                        or binding['category'] != 'rigid'
                        or type(binding['min']) is not int or type(binding['max']) is not int
                        or not 1 <= binding['min'] <= binding['max'] <= 100):
                    raise ValueError('label templates require an explicit prefix/placeholder, rigid category and bounded count')
                if self.repeat_counts and ident in self.repeat_counts:
                    raise ValueError('a stage cannot have both numeric and object-label repeats')
                if any(ident in b for choice in self.choices for b in choice.branches):
                    raise ValueError('object-label templates inside choice branches require explicit branch compilation')
        if self.repeat_counts is not None:
            if not isinstance(self.repeat_counts, dict) or set(self.repeat_counts) - stage_ids:
                raise ValueError('repeat_counts must reference existing action stages')
            for binding in self.repeat_counts.values():
                if (not isinstance(binding, dict) or set(binding) != {'label','min','max'}
                        or not isinstance(binding['label'], str) or not binding['label']
                        or type(binding['min']) is not int or type(binding['max']) is not int
                        or not 1 <= binding['min'] <= binding['max'] <= 100):
                    raise ValueError('repeat counts require label and finite integer bounds 1 <= min <= max <= 100')
        if self.stage_dependencies is None:
            if self.gates or self.choices:
                raise ValueError('programs with scene gates or choices require explicit stage_dependencies')
            return
        ids = stage_ids | gate_ids | choice_ids
        deps = self.stage_dependencies
        if not isinstance(deps, dict) or set(deps) != ids:
            raise ValueError('stage_dependencies must define every stage exactly once')
        for stage_id, parents in deps.items():
            if (not isinstance(parents, list) or any(not isinstance(p, str) or p not in ids for p in parents)
                    or len(parents) != len(set(parents)) or stage_id in parents):
                raise ValueError('stage dependencies require unique existing parents, excluding self')
        pending, done = set(ids), set()
        while pending:
            ready = {s for s in pending if set(deps[s]) <= done}
            if not ready:
                raise ValueError('stage_dependencies contains a cycle')
            done.update(ready)
            pending.difference_update(ready)
        membership={}
        for choice in self.choices:
            if deps[choice.id] != [branch[-1] for branch in choice.branches]:
                raise ValueError('choice dependencies must list its branch terminals in branch order')
            for index,branch in enumerate(choice.branches):
                if set(branch)-stage_ids:
                    raise ValueError('choice branches must name concrete action stages')
                for ident in branch:
                    if ident in membership:
                        raise ValueError('an action can belong to only one choice branch')
                    membership[ident]=(choice.id,index)
                ancestors=set()
                todo=list(deps[branch[-1]])
                while todo:
                    ident=todo.pop()
                    if ident not in ancestors:
                        ancestors.add(ident);todo.extend(deps[ident])
                if not set(branch[:-1])<=ancestors:
                    raise ValueError('choice terminal must depend on every earlier branch action')
        for ident,parents in deps.items():
            for parent in parents:
                if parent in membership and ident not in choice_ids and membership.get(ident)!=membership[parent]:
                    raise ValueError('external successors must depend on the choice node, not an optional branch')

    def dependencies(self):
        if self.stage_dependencies is not None:
            return deepcopy(self.stage_dependencies)
        return {s.id: ([] if i == 0 else [self.stages[i - 1].id])
                for i, s in enumerate(self.stages)}

    def bind(self, env, env_idx):
        from task.atomic.bindings import expand_label_templates, expand_repeats
        return expand_repeats(expand_label_templates(self, env, env_idx), env, env_idx)

    @classmethod
    def load(cls, path):
        data = _read_json(path)
        if not data.get("task_name"):
            raise ValueError("atomic program needs task_name")
        stages = tuple(AtomicStage.from_dict(stage) for stage in data.get("stages", ()))
        if not stages or len({stage.id for stage in stages}) != len(stages):
            raise ValueError("atomic program needs unique, nonempty stages")
        instruction = data.get("instruction")
        if instruction is not None and (not isinstance(instruction, str) or not instruction.strip()):
            raise ValueError("program instruction must be a nonempty string")
        geometric_instruction = data.get('geometric_instruction')
        if geometric_instruction is not None and (not isinstance(geometric_instruction, str) or not geometric_instruction.strip()):
            raise ValueError('geometric_instruction must be nonempty text')
        gates = tuple(AtomicGate.from_dict(g) for g in data.get('gates', ()))
        choices = tuple(AtomicChoice.from_dict(c) for c in data.get('choices', ()))
        return cls(data["task_name"], stages, instruction, geometric_instruction,
                   deepcopy(data.get('stage_dependencies')), deepcopy(data.get('repeat_counts')), gates, None, choices,
                   deepcopy(data.get('label_templates')))

    def stage(self, stage_id):
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        raise ValueError(f"unknown atomic stage {stage_id!r} for {self.task_name}")


@dataclass(frozen=True)
class AtomicGate:
    id: str
    checks: tuple

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {'id','checks'} or not isinstance(data['id'], str) or not data['id']:
            raise ValueError('gate requires id and read-only checks')
        checks = tuple(deepcopy(data['checks']))
        if not checks:
            raise ValueError('gate requires at least one read-only check')
        for check in checks:
            _validate_check(check)
        return cls(data['id'], checks)


@dataclass(frozen=True)
class AtomicChoice:
    id: str
    branches: tuple[tuple[str, ...], ...]
    required: int

    @classmethod
    def from_dict(cls,data):
        if not isinstance(data,dict) or set(data)!={'id','branches','required'} or not isinstance(data['id'],str) or not data['id']:
            raise ValueError('choice requires id, branches and required count')
        branches=data['branches']
        if (not isinstance(branches,list) or len(branches)<2 or any(not isinstance(b,list) or not b or
                any(not isinstance(s,str) or not s for s in b) for b in branches)):
            raise ValueError('choice requires at least two nonempty action branches')
        ids=[s for b in branches for s in b]
        if len(ids)!=len(set(ids)) or type(data['required']) is not int or not 1<=data['required']<len(branches):
            raise ValueError('choice branch actions must be distinct and 1 <= required < branches')
        return cls(data['id'],tuple(tuple(b) for b in branches),data['required'])


@dataclass(frozen=True)
class AtomicTrace:
    task_name: str
    layout_id: int
    actions: tuple[dict, ...]
    stage_starts: dict[str, int]

    @classmethod
    def load(cls, path):
        data = _read_json(path)
        actions = data.get("actions", [])
        starts = data.get("stage_starts", {})
        if not data.get("task_name") or not isinstance(actions, list) or not isinstance(starts, dict):
            raise ValueError("trace needs task_name, actions list, and stage_starts mapping")
        if not isinstance(data.get("layout_id"), int):
            raise ValueError("trace needs an integer layout_id")
        if any(not isinstance(action, dict) for action in actions):
            raise ValueError("trace actions must be dictionaries")
        if any(not isinstance(index, int) or index < 0 or index > len(actions) for index in starts.values()):
            raise ValueError("stage_starts indices must be valid action boundaries")
        return cls(data["task_name"], data["layout_id"], tuple(actions), starts)


def load_variant(path):
    return _read_json(path) if path else None
