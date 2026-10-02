"""Protect task semantics that a flat pick/place catalogue cannot express."""
from copy import deepcopy
import json
import unittest

from scripts.atomic.segmentation_plans import PLANS, REPORT, render, validate, walk_flow


class SegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PLANS.read_text())
        cls.plans = {entry['task']: entry for entry in cls.data['tasks']}

    def test_complete_inventory_and_source_config_freshness(self):
        validate(self.data)
        self.assertEqual(len(self.plans), 54)
        self.assertEqual(REPORT.read_text(), render(self.data))
        for section in ('source', 'config'):
            stale = deepcopy(self.data)
            stale['tasks'][0]['evidence'][section]['sha256'] = 'changed'
            with self.subTest(section=section), self.assertRaisesRegex(ValueError, 'stale plan source/config'):
                validate(stale)
        incomplete = deepcopy(self.data)
        incomplete['tasks'].pop()
        with self.assertRaisesRegex(ValueError, 'coverage mismatch'):
            validate(incomplete)

    def test_fixed_geometry_cannot_be_a_pick_target(self):
        data = deepcopy(self.data)
        screw = next(p for p in data['tasks'] if p['task'] == 'fasten_screws')
        pick = next(n for n in walk_flow(screw['flow']) if n.get('family') == 'pick')
        self.assertEqual(pick['binding'], 'nuts')
        pick['binding'] = 'bolts'
        with self.assertRaisesRegex(ValueError, 'not fixed Geometry'):
            validate(data, check_evidence=False)

    def test_native_button_cycles_have_two_confirmations(self):
        flow = self.plans['press_by_number']['flow']
        self.assertEqual(flow['type'], 'sequence')
        steps = flow['children']
        self.assertEqual([n['type'] for n in steps], ['repeat', 'action', 'repeat', 'action'])
        self.assertEqual([steps[1]['binding'], steps[3]['binding']], ['blue', 'blue'])
        self.assertEqual([steps[0]['selection'], steps[2]['selection']], ['card0_count', 'card1_count'])
        self.assertTrue(all('release' in n['goal'] for n in walk_flow(flow) if n['type'] == 'action'))

    def test_free_item_order_subset_selection_and_sustained_hold(self):
        digits = self.plans['arrange_largest_number']['flow']
        self.assertEqual(digits['order'], 'any')
        self.assertEqual(digits['body']['type'], 'sequence')
        toast = self.plans['make_toast']['flow']['children'][0]
        self.assertEqual(toast['selection'], 'choose_two')
        self.assertEqual(len(self.plans['make_toast']['bindings']['bread']['labels']), 4)
        pen = self.plans['fill_pen_holder']['flow']['children'][1]
        self.assertEqual((pen['type'], pen['binding']), ('maintain', 'holder'))
        self.assertEqual(pen['body']['binding'], 'pens')
        self.assertEqual(self.plans['organize_table']['flow']['type'], 'independent')

    def test_throw_stays_unsupported_and_game_events_are_not_actions(self):
        dustbin = list(walk_flow(self.plans['put_bottles_into_dustbin']['flow']))
        self.assertEqual([n['behavior'] for n in dustbin if n['type'] == 'unsupported'], ['throw'])
        self.assertNotIn('place', [n['family'] for n in dustbin if n['type'] == 'action'])
        game = list(walk_flow(self.plans['play_tic_tac_toe']['flow']))
        self.assertIn('opponent_turn', [n['name'] for n in game if n['type'] == 'event'])
        self.assertEqual({n['family'] for n in game if n['type'] == 'action'}, {'pick', 'place'})
        data = deepcopy(self.data)
        data['tasks'][0]['status'] = 'observed'
        with self.assertRaisesRegex(ValueError, 'source-only'):
            validate(data, check_evidence=False)


if __name__ == '__main__':
    unittest.main()
