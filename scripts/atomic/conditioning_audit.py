#!/usr/bin/env python3
"""Record every taxonomy slot/modifier cell and reject stale audit artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from task.atomic.spec import FAMILIES, GEOMETRY_KINDS
from scripts.atomic.storage import atomic_write_json, atomic_write_text

FAMILY_NAMES = dict(zip(
    ['Pick', 'Place', 'Push', 'Push with tool / sweep', 'Pour', 'Actuate', 'Twist',
     'Insert', 'Touch with tool', 'Handover', 'Fold'],
    ['pick', 'place', 'push', 'push_with_tool', 'pour', 'actuate', 'twist',
     'insert', 'touch_with_tool', 'handover', 'fold']))
FACTORS = dict(zip('PTDOR', ['point', 'pose', 'relative_displacement',
                           'relative_orientation', 'spatial_relation']))
JSON_PATH = REPO / 'task/atomic/conditioning_audit.json'
MD_PATH = REPO / 'task/atomic/CONDITIONING_AUDIT.md'

# Each slot is reviewed explicitly. Codes describe measurement/event readiness,
# independently of whether that family's action recognizer exists.
PROFILES = {
    'selection': ('S', 'Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates.'),
    'contact': ('C', 'Actual same-step finger/object manifold points. P/D/R can score contact location. T/O require a separate physical frame plus contact evidence, not an orientation on a point.'),
    'goal': ('G', 'Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate.'),
    'approach': ('G', 'before_contact retains the synchronized point/frame and reference from the step immediately preceding actual contact. held_tool_strike measures target-relative pre-impact velocity, actual landmark-scoped impact and held separation/retraction. Offline counterexamples; physical frame/normal calibration and live evidence remain.'),
    'release': ('G', 'supported_release emits object-specific release and settled events after held transport, all-finger release, support and bounded pose changes. Live rigid geometry can be sampled at either event. Offline counterexamples; task binding/calibration and live verification remain.'),
    'tool': ('G', 'Actual tool/target collision pairs and calibrated active tip/edge frames are distinct from finger/tool grasp. Object-pair contact locations and functional-frame geometry are implemented; post-scene-load report enablement fixes the missing task-body APIs. Active-part calibration and fresh live recognition/geometry validation remain.'),
    'path': ('G', 'TrajectoryObserver samples an explicit physical landmark each physics substep between declared events; records max/RMS polyline deviation, ordered waypoint witnesses, backtracking and coverage failures. Raw samples reproduce offline. Active sweep-tip calibration, feasibility and live validation remain; no inference between unsampled physics states.'),
    'spout': ('G', 'Rigid functional-frame math available only after verifying a real mouth/spout tag and transfer event. A vessel centre is not a spout; no live spout evidence.'),
    'stream': ('G', 'Persistent source-qualified material crossings measure XY opening error, aperture overrun, relative velocity direction and speed. Raw consecutive physics samples reproduce independently; excessive opening rotation or gaps are unscored. Vessel cavity/mouth calibration and fresh liquid USD readback validation remain. Nominal particle mass is not measured liquid volume or density.'),
    'link': ('G', 'PhysX link frames, annotated moving-control joint binding, contact-coupled motion/press-release events and live child mesh geometry implemented. P/D/R use moving-link contacts. T/O require an oriented physical frame plus contact evidence. Link supported-on scopes signed support contacts to exact selected bodies. Per-asset calibration and live verification remain.'),
    'twist': ('G', 'contact_constrained_twist measures unwrapped signed substep rotation only during verified grip, part/target contact, pivot radius/depth and bounded off-axis motion. Pivot/axis/contact geometry requires calibrated asset frames. Failed attempts retain depth/radius but no fabricated angle; final orientation alone cannot recognize a twist. Live binding remains.'),
    'entry': ('G', 'Annotated tip/opening frame math and charger-specific entry predicates exist. Other assets need verified frames/clearance/crossing adapters; charger entry was not reached in the pilot.'),
    'handover': ('G', 'grip_transfer emits giver_hold, overlap and receiver_only transitions from actual named-arm contacts. Live object frames/positions can be sampled at those events. Offline counterexamples; task arm/frame bindings and live verification remain.'),
    'deformable': ('G', 'Stable material IDs support actual cloth points, tagged tangent frames and two-landmark crease frames. CPU readback requires running cloth and Fabric disabled; GPU tensors require initialized PhysX views. cloth_landmark_fold recognizes newly lifted/bent/closed/stable material deformation, not finger contact or full layer/self-intersection correctness. Offline counterexamples passed; selected material patch layer geometry is implemented, with live validation pending.'),
    'categorical': ('NA', 'Categorical/material identity; geometry belongs on another named slot. Amount, flow, joint travel and twist angle are separate intrinsic parameters.'),
}
SLOTS = {
    'pick': {'object': 'selection', 'grasp region': 'contact', 'lift goal': 'goal'},
    'place': {'object': 'selection', 'target': 'goal', 'object goal': 'goal', 'release point': 'release'},
    'push': {'object': 'selection', 'contact': 'contact', 'hand approach': 'approach', 'goal': 'goal'},
    'push_with_tool': {'tool': 'selection', 'object(s)': 'selection', 'tool tip': 'tool',
                       'start contact': 'tool', 'sweep segment': 'path', 'goal': 'goal'},
    'pour': {'contents': 'categorical', 'source': 'selection', 'destination': 'selection',
             'spout': 'spout', 'opening': 'stream', 'tilt': 'spout', 'source pour pose': 'goal'},
    'actuate': {'mechanism': 'selection', 'control': 'selection', 'contact': 'link',
                'approach': 'link', 'state': 'link'},
    'twist': {'part': 'selection', 'axis/pivot': 'twist', 'contact': 'twist', 'orientation': 'twist'},
    'insert': {'object': 'selection', 'receptacle': 'selection', 'opening': 'entry',
               'alignment': 'entry', 'goal': 'entry'},
    'touch_with_tool': {'target': 'selection', 'contact': 'tool', 'tool': 'selection',
                        'tool tip': 'tool', 'approach': 'approach'},
    'handover': {'object': 'selection', 'giver': 'categorical', 'receiver': 'categorical',
                 'exchange': 'handover', 'object orientation': 'handover'},
    'fold': {'deformable': 'deformable', 'crease': 'deformable', 'moving region': 'deformable',
             'target region': 'deformable', 'grasp point': 'deformable', 'final orientation': 'deformable'},
}
LIVE = {
    ('pick', 'object', 'P'): 'The geometry-selection-query-rpc-1006 block pair resolved the same unique initial XYZ candidate from a bounded live layout query, reproduced inventory/point binding and recognized first sustained selected-object contact. Both arms selected the wrong first block. This validates this initial point selection contract, not arbitrary language/control roles.',
    ('pick', 'grasp region', 'D'): 'Cup/charger pilot and later mallet grasp-band scores observed. The tool-contact mallet baseline retained a contact-held lift and 2.30 mm worst-point height error. Scissors lift event remained unobserved. Applies to these finger contacts, not every pick/asset.',
    ('push', 'contact', 'D'): 'Baseline T first-motion finger-contact score observed; conditioned run lacked finger evidence at that event.',
    ('push', 'goal', 'T'): 'Conditioned T goal pose scored; push interaction remained unverified. Goal geometry is not action recognition.',
    ('pour', 'source pour pose', 'O'): 'Cup local-z direction relative to vase observed at first whole-ball entry in conditioned run.',
    ('pour', 'source pour pose', 'R'): 'Cup/vase height and projected footprint overlap observed at first whole-ball entry in conditioned run.',
    ('pour', 'source pour pose', 'T'): 'The geometry-liquid-populated-rpc-1006 pair measured the asset-bound bottle mouth against the asset-bound cup opening at first qualified cohort transfer: 38.60/28.25 mm translation and 164.49/171.72 degrees full orientation. Both reproduce; native success true/false. Historical per-particle source holds/initial region frames are partial evidence. This validates these mouth frames and measured SE(3) values, not passage through the source mouth or whole-fluid transfer.',
    ('touch_with_tool', 'contact', 'D'): 'The geometry-tool-contacts-1006 xylophone baseline retained eight held impacts/retractions and actual mallet/xylophone contact-location errors of 1.23–6.33 mm. Raw contact, approach-speed and retraction-pose witnesses passed a separate consistency validator. Native task failed. The conditioned partner has seven consistent strike windows and one incompatible aborted-impact/completion window, excluded from scalar summaries. Current runtime archives interrupted event scores/paths and binds retries by attempt ID. This covers these impacts, not every tool/asset or musical timing.',
    ('fold', 'crease', 'R'): 'The geometry-material-curves-rpc-1006 matched pair reproduced full connected material-edge Hausdorff errors of 35.09/58.89/70.33 mm baseline and 44.66/27.10/46.58 mm conditioned. Both native tasks failed; the conditioned left-sleeve observer completed. Earlier finite-chord evidence remains separate. This validates the selected anchored path geometry, not discovery of a newly formed physical crease or grasp force.',
    ('fold', 'moving region', 'R'): 'Actual model/topology-bound patches measured coverage and horizontal gap in geometry-cloth-patches-1006 conditioned and geometry-crease-segments-1006 baseline episodes. Zero overlap leaves vertical gaps unobserved; body-patch coverage 0.0553 in the chord baseline had 13.8–38.7 mm overlapping-region gaps. These belong to distinct completed frozen comparisons. No whole-garment layering or grasp-force claim.',
    ('fold', 'target region', 'R'): 'Actual fixed-ID target material patches served as the live references in the same patch/chord episodes, with coverage, planar distance and overlapping-region gap reproduction. This applies to these selected material regions; full layer order, force-bearing contact and global self-intersection remain unresolved.',
    ('fold', 'final orientation', 'O'): 'The geometry-surface-gaps-1006 conditioned episode measured actual material tangent-normal direction errors for all three observers, independently reproduced. This covers the declared local normal axes, not every global cloth orientation or physical grasp. Native task and all fold observers failed; scalar final geometry remained observed.',
}
LIVE_EVIDENCE = {
    ('pick', 'object', 'P'): 'task/atomic/EXPANSION_STATUS.md#execution-ledger',
    ('pour', 'source pour pose', 'T'): 'task/atomic/GEOMETRIC_MEASUREMENT.md#material-source-witness-validation',
    ('touch_with_tool', 'contact', 'D'): 'task/atomic/EXPANSION_STATUS.md#live-held-strike-witness-validation',
    ('fold', 'crease', 'R'): 'task/atomic/GEOMETRIC_MEASUREMENT.md#live-cloth-validation-and-component-observation',
    ('fold', 'moving region', 'R'): 'task/atomic/GEOMETRIC_MEASUREMENT.md#live-cloth-validation-and-component-observation',
    ('fold', 'target region', 'R'): 'task/atomic/GEOMETRIC_MEASUREMENT.md#live-cloth-validation-and-component-observation',
    ('fold', 'final orientation', 'O'): 'task/atomic/EXPANSION_STATUS.md#live-selected-surface-gap-validation',
}


def build():
    path = REPO / 'task/atomic/TAXONOMY.md'
    rows, family = [], None
    for line in path.read_text().splitlines():
        if line.startswith('**') and ' —' in line:
            family = FAMILY_NAMES[line.split(' —')[0].strip('*')]
        if not line.startswith('| `['):
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if len(cells) != 6:
            raise ValueError('taxonomy slot tables must have exactly five factor columns')
        slot = re.search(r'\[([^]]+)\]', cells[0]).group(1)
        profile = SLOTS[family][slot]
        code, note = PROFILES[profile]
        factors = {}
        for factor, concept in zip(FACTORS, cells[1:]):
            status = 'NA' if concept == '—' else code
            detail = note if concept != '—' or profile == 'categorical' else 'No meaningful condition of this geometric type on this slot; intrinsic/context parameters are scored separately.'
            if status == 'C' and factor in 'TO':
                status = 'F'
            if family == 'pick' and slot == 'lift goal' and factor == 'D':
                status, detail = 'G', 'Reference time=stage_start freezes the actual landmark frame for lift displacement; root/centre pose and historical rigid footprints remain fixed. Local regression tested; no new live snapshot evidence. This is not a referent-selection adapter.'
            if family == 'push' and slot == 'goal' and factor == 'D':
                detail += ' Stage-start offsets use reference time=stage_start; episode-start state across later stages still requires a separately retained snapshot.'
            if profile == 'tool' and slot in ('start contact', 'contact') and factor in 'PDR' and concept != '—':
                status, detail = 'G', 'Force-bearing object_contact_points resolves explicit tool/target pairs; first_contact records synchronized points/impulses. held_tool_push and held_tool_contact provide held stroke/contact evidence offline. held_tool_strike adds pre-impact approach speed and held retraction after impact; active-part calibration, musical timing and live verification remain. Contacts have no orientation.'
            if profile == 'tool' and slot in ('start contact','contact') and factor in 'TO' and concept != '—':
                status, detail = 'F', 'Actual contact points have no orientation. Use a separately calibrated physical tool/target frame and independently verify the contact event.'
            if family == 'insert' and slot in ('opening', 'alignment', 'goal') and factor == 'R' and concept != '—':
                status, detail = 'G', 'inside_aperture measures an actual closed-solid cross-section; inside_trace_aperture separately measures closed consistently directed actual material traces at one live calibrated plane, even when remote mesh ends are open. Explicit material paths, directed degree/winding and noncrossing traces are required. Both preserve aperture holes and planar clearance; local traces do not certify whole-solid volume. held_insertion separately requires outside-to-inside depth, hold and target contact. Annotated seat/rim poses measure gap/alignment but do not prove thread engagement or seating force. through/flush are not unrestricted generic relation names; live calibration remains.'
            if family == 'fold' and slot == 'grasp point' and concept != '—':
                status, detail = 'M', 'Actual finger/cloth-particle contact correspondence is unavailable. Material landmarks, EEF proximity and deformation cannot substitute for a measured cloth grasp contact.'
            if family == 'fold' and factor == 'R' and slot in ('moving region','target region','crease') and concept != '—':
                status, detail = ('G', 'Finite endpoint chords and ordered persistent mesh-edge paths support intersection gap and symmetric Hausdorff coincidence. Curve Hausdorff includes every edge interior; endpoint/vertex-set proxies fail counterexamples. Model-bound authored paths are calibrated for all three garment models with actual file/topology hash checks. This measures declared material curves, not discovery of a new physical crease or whole-cloth self-intersection; live validation remains.') if slot=='crease' else ('G','Explicit persistent material topology faces support projected moving-patch coverage and all triangle-pair layer gap extrema. Overhang and penetrations hidden by a single landmark are rejected. This certifies selected-patch layering, not finger force or global cloth self-intersection; 30 mm same-side geodesic patches are bound for all three baked Top_Long models with live asset/topology hash checks; policy validation remains pending.')
            if family == 'pour' and slot == 'tilt' and concept != '—':
                detail = 'Use source vessel orientation for T/O and a verified spout point for R. Generic rigid math exists; no spout or stream measurement was observed live.'
            live = LIVE.get((family, slot, factor))
            if live:
                status, detail = 'L', live
            factors[factor] = {'kind': FACTORS[factor], 'concept': concept,
                               'status': status, 'audit': detail,
                               'live_evidence': LIVE_EVIDENCE.get((family, slot, factor), 'task/atomic/PILOT_RESULTS.md') if live else None}
        rows.append({'family': family, 'slot': slot, 'profile': profile, 'factors': factors})
    actual = {(row['family'], row['slot']) for row in rows}
    expected = {(family, slot) for family, slots in SLOTS.items() for slot in slots}
    if len(actual) != len(rows) or actual != expected or set(SLOTS) != FAMILIES or set(FACTORS.values()) != GEOMETRY_KINDS:
        raise ValueError('taxonomy/action/slot/factor coverage changed; review every missing or new cell')
    fingerprints = {str(p): hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in (
        Path('task/atomic/TAXONOMY.md'), Path('task/atomic/spec.py'), Path('task/atomic/geometry.py'),
        Path('task/atomic/session.py'), Path('task/atomic/surfaces.py'), Path('task/atomic/contacts.py'),
        Path('task/atomic/recognizers.py'), Path('task/atomic/recognition_validation.py'), Path('task/atomic/material_validation.py'), Path('task/atomic/bindings.py'), Path('task/atomic/landmarks.py'), Path('task/atomic/materials.py'), Path('task/atomic/selection.py'), Path('task/atomic/trajectory.py'), Path('task/atomic/regions.py'), Path('task/atomic/fit.py'), Path('task/atomic/flow.py'), Path('task/atomic/fold.py'), Path('task/atomic/layers.py'), Path('task/atomic/segments.py'), Path('task/atomic/curves.py'), Path('task/atomic/surface_distance.py'), Path('task/atomic/cloth_calibration.py'), Path('task/atomic/calibration.py'), Path('task/atomic/model_frames.py'), Path('env/scene_manager/objects/fluid.py'), Path('env/scene_manager/objects/garment.py'))}
    counts = {code: sum(cell['status'] == code for row in rows for cell in row['factors'].values())
              for code in ('L', 'C', 'G', 'F', 'S', 'M', 'NA')}
    return {'schema_version': 1, 'scope': 'source/semantics audit, not universal live validation',
            'source_sha256': fingerprints, 'families': len(FAMILIES), 'slots': len(rows),
            'factor_cells': len(rows) * len(FACTORS), 'status_counts': counts, 'rows': rows}


def render(data):
    lines = ['# Conditioning coverage: every action slot and factor', '',
             f"Reviewed **{data['families']} action families, {data['slots']} family-specific slots and 5 geometric factors**, "
             f"i.e. **{data['factor_cells']} individual slot/factor cells** (including inapplicable cells). "
             'The [machine-readable audit](conditioning_audit.json) stores the concept, status and reasoning for each cell. '
             'Source fingerprints and exact slot coverage make omissions or stale artifacts detectable.', '',
             'This is a complete **source/semantics coverage audit**, not a claim that every combination has a '
             'working adapter or live experiment. See [family recognition audit](ACTION_AUDIT.md), '
             '[all task examples](TASK_MAP.md) and [taxonomy matrices](TAXONOMY.md).', '',
             '## Status meanings', '', '| Code | Meaning | Cells |', '| --- | --- | --- |']
    meanings = {'L': 'Specific retained simulator measurement observed and independently reproduced; not universal live validation.',
                'C': 'Finger contact location checker available; cell-specific live evidence absent.',
                'G': 'Generic rigid point/frame/relation math and selectors available; calibrated assets/events and family wiring still needed.',
                'F': 'Contact point has no orientation: use a separate physical frame and independent contact evidence.',
                'S': 'Explicit object candidate snapshots/contact identity supported; automatic and landmark-specific selection remain.',
                'M': 'Required measurement, event, trajectory, initial frame or relation adapter missing.',
                'NA': 'Modifier does not apply to this categorical/intrinsic slot.'}
    for code, meaning in meanings.items():
        lines.append(f"| **{code}** | {meaning} | {data['status_counts'][code]} |")
    lines += ['', '**L/C/G refer to geometric measurement capability, not completed action recognition.** '
              'A native predicate can be true without the interaction. L applies only to the exact contact/event/asset '
              f"described in its JSON evidence; the {data['status_counts']['L']} L cells are not universally validated slots.", '',
              '## Exhaustive slot × factor matrix', '',
              'P = 3D point; T = SE(3) pose; D = landmark-relative displacement; '
              'O = landmark-relative orientation; R = spatial relation.', '',
              '| Family | Slot | P | T | D | O | R | Required semantics / limitation |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in data['rows']:
        notes = list(dict.fromkeys(cell['audit'] for cell in row['factors'].values() if cell['status'] != 'NA'))
        if not notes:
            notes = [PROFILES[row['profile']][1]]
        lines.append('| `' + row['family'] + '` | `[' + row['slot'] + ']` | ' +
                     ' | '.join(row['factors'][factor]['status'] for factor in FACTORS) +
                     ' | ' + ' '.join(notes) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    data = build()
    generated = render(data)
    # Checker details are authored below the generated matrix, kept in one file.
    marker = '\n## Factor-level checker audit\n'
    existing = MD_PATH.read_text() if MD_PATH.exists() else ''
    details = marker + existing.split(marker, 1)[1] if marker in existing else ''
    expected = generated + details
    if args.refresh:
        atomic_write_json(JSON_PATH, data)
        atomic_write_text(MD_PATH, expected)
    elif json.loads(JSON_PATH.read_text()) != data or existing != expected:
        raise ValueError('stale conditioning audit: review changed sources/slots, then --refresh')
    print(f"Verified {data['families']} families, {data['slots']} slots and {data['factor_cells']} factor cells; {data['status_counts']}")


if __name__ == '__main__':
    main()
