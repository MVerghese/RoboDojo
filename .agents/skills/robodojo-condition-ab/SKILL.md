---
name: robodojo-condition-ab
description: Define RoboDojo geometric conditions and generate controlled with/without-prompt A/B suites or selected-stage steering trials. Use for prompt/measurement alignment, target calibration and matched pair design.
---

# RoboDojo conditioning and A/B design

Read `task/atomic/CONDITIONING_AB.md` in the checkout for executable commands;
consult `TAXONOMY.md` and the requested family's `ACTION_AUDIT.md` row to determine
valid slots and instrumentation gaps.

1. Define the measurement, reference frame, axes, event, target and tolerance in
   a complete program. Inspect actual asset/landmark geometry for feasibility.
   Contact points have no pose orientation; mesh centre, body root and annotated
   tip/opening are distinct. Success checks describe the action independently.
2. Choose full-task or selected-stage prompting. Full-task `geometric_instruction`
   appends to the native resolved instruction; top-level `instruction` replaces
   it. Stage mode receives stage/variant `instruction`, not the full-task append.
   Recording stage boundaries does not automatically switch prompts.
3. For full-task pairs use `scripts/atomic/generate_ab_suite.py` with a complete
   shared program and matching text file. For the established four-task pilot use
   `generate_paired_suite.py`. Output to a fresh directory; both arms must score
   the same geometry and differ only in the geometric text.
4. For a stage-only pair, put geometry in the shared program with an unconditioned
   stage instruction. Change only the conditioned variant instruction; use the
   same prefix trace, layout and checkpoint. A later stage requires a successful
   layout-linked trace with all earlier boundaries, not dataset video metadata.
5. Validate the suite using `scripts.atomic.run_suite.validate_suite` before
   scheduling. Review prompt text against every numerical field; schema checking
   alone cannot establish semantic agreement.

Keep checkpoint, inference settings, runtime, seed/layout, traces and recognition
definitions fixed. The present suite runner supports one episode per case on
layout/seed 0. The 21-case `generate_suite.py` sweep changes targets and is
exploratory, not a matched with/without-prompt comparison.

When reviewing results, verify the **delivered** `policy_prompt_history`, not
just the manifest. Report native success, recognition, continuous error and
event coverage separately. Offline target rescoring does not test policy
steering. Missing events/contact have no score/pass. One episode per arm
demonstrates integration, not a statistical steering effect.
