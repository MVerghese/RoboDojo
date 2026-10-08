"""Explicit corrections of historical slot metadata; measured values stay intact."""


def condition_slot(stage,condition):
    declared=condition.get('slot');recognition=stage.get('recognition') or {}
    opening=(recognition.get('source_exit') or {}).get('opening')
    if (stage.get('family')=='pour' and declared=='source pour pose' and opening is not None
            and condition.get('measurement')==opening):
        return 'spout',{'status':'corrected_metadata','declared_slot':declared,'effective_slot':'spout',
            'reason':'measurement exactly matches this recognizer\'s calibrated source-mouth opening; taxonomy vessel frame/center is a distinct slot',
            'scope':'report grouping correction only; frozen definitions, measurements, policy prompts and outcomes retained'}
    return declared,None
