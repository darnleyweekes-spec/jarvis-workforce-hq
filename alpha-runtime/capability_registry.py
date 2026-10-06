"""Pinned ALPHA capabilities and permission-scoped handoffs.

Registration does not imply deployment. This module never starts a service.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from alpha_runtime import SQLiteMissionStore, MissionError

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / 'integrations' / 'capabilities.json'


def load_capabilities(path=DEFAULT_MANIFEST):
    data = json.loads(Path(path).read_text())
    capabilities = {}
    for item in data['capabilities']:
        key = item['id']
        if key in capabilities or not re.fullmatch(r'[a-z0-9-]+', key):
            raise ValueError('Invalid or duplicate capability ID')
        if not re.fullmatch(r'[0-9a-f]{40}', item['commit']):
            raise ValueError('Source must be pinned to a commit')
        if not item['repository'].startswith('https://github.com/darnleyweekes-spec/'):
            raise ValueError('Expected an approved user fork')
        if item['status'] not in {'source_ready', 'library_verified', 'blocked'}:
            raise ValueError('Unsupported installation status')
        capabilities[key] = item
    return capabilities


def prepare_capability(store: SQLiteMissionStore, mission_id: str, capability_id: str,
                       manifest=DEFAULT_MANIFEST):
    capability = load_capabilities(manifest)[capability_id]
    if not store.verify_event_chain(mission_id):
        raise MissionError('Invalid mission ledger')
    mission = store.get(mission_id)
    permission = capability_id + '.prepare'
    if permission not in mission['request']['allowed_tools']:
        raise MissionError('Mission does not permit ' + permission)
    return {
        'capability': capability,
        'mission_id': mission_id,
        'objective': mission['request']['objective'],
        'success_criteria': mission['request']['success_criteria'],
        'constraints': mission['request']['constraints'],
        'prohibited_actions': mission['request']['prohibited_actions'],
        'mission_state': mission['mission_state'],
        'evidence': mission['evidence'],
        'execution_authorized': False,
        'independent_verification_required': True,
        'remaining_setup': capability['blockers'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    for key, item in load_capabilities(args.manifest).items():
        print(key + ': ' + item['status'] + ' | ' + '; '.join(item['blockers']))

if __name__ == '__main__':
    main()
