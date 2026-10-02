"""Preserve the previous report when an output write fails or is interrupted."""
import json
import os
from pathlib import Path
import tempfile


def atomic_write_text(path, text):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', delete=False) as output:
            temporary = Path(output.name)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_json(path, payload):
    atomic_write_text(path, json.dumps(payload, indent=2) + '\n')
