"""Assemble the two Kaggle datasets that the blind runs use. Only DEVELOPMENT missions are copied, so the sealed missions
never reach the agent: AEOSSP train case_0001-0007 (cases + worlds), Revisit train case_0001-0004 (cases).
Output: work/kaggle/<name>/{task_<x>/, pack/, wheels/ (put brahe 1.8.0 manylinux wheels here), dataset-metadata.json}.
Usage: python data/build_kaggle_datasets.py <kaggle_user>"""
import os, sys, shutil, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT, WORK, AEOSSP_PACK, REVISIT_DATA
user = sys.argv[1] if len(sys.argv) > 1 else 'your-kaggle-user'
ign = shutil.ignore_patterns('__pycache__', '*.pyc', 'metrics.json', 'correct.json')
for name, task, dev, src_cases, src_worlds in (
        ('aeossp-blind-task', 'aeossp', [f'case_{i:04d}' for i in range(1, 8)], os.path.join(AEOSSP_PACK, 'cases', 'train'), os.path.join(AEOSSP_PACK, 'worlds', 'train')),
        ('revisit-blind-task', 'revisit', [f'case_{i:04d}' for i in range(1, 5)], os.path.join(REVISIT_DATA, 'cases', 'train'), None)):
    out = os.path.join(WORK, 'kaggle', name); shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, 'tasks', task), os.path.join(out, f'task_{task}'), ignore=ign)
    for c in dev:
        shutil.copytree(os.path.join(src_cases, c), os.path.join(out, 'pack', 'cases', 'train', c))
        if src_worlds: shutil.copytree(os.path.join(src_worlds, c), os.path.join(out, 'pack', 'worlds', 'train', c))
    os.makedirs(os.path.join(out, 'wheels'), exist_ok=True)
    json.dump({'title': name.replace('-', ' '), 'id': f'{user}/{name}', 'licenses': [{'name': 'other'}]}, open(os.path.join(out, 'dataset-metadata.json'), 'w'))
    print(name, '->', out, '| dev missions:', len(dev))
