"""Repository paths. Override with environment variables:
  AAB_DIR  AstroAgentBench checkout            (default: external/AstroAgentBench, made by `make fetch`)
  MS_WORK  generated data (packs, runs, replays) (default: work/)
  FFMPEG   ffmpeg binary for the videos          (default: ffmpeg on PATH)"""
import os
ROOT = os.path.dirname(os.path.abspath(__file__))
AAB = os.environ.get('AAB_DIR', os.path.join(ROOT, 'external', 'AstroAgentBench'))
WORK = os.environ.get('MS_WORK', os.path.join(ROOT, 'work'))
ASSETS = os.path.join(ROOT, 'assets')
FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
AEOSSP_PACK = os.path.join(WORK, 'aeossp', 'pack')          # cases/ (link to AAB) + worlds/
REVISIT_DATA = os.path.join(AAB, 'benchmarks', 'revisit_constellation', 'dataset')
