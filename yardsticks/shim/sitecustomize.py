"""Sandbox shim for Phase 0 only: the sandbox forbids POSIX semaphores, so process pools cannot start.
Replace ProcessPoolExecutor with a thread pool (same results, different parallelism). Solver code is unchanged."""
import concurrent.futures as _cf, concurrent.futures.process as _cfp
class _ThreadPoolAsProcessPool(_cf.ThreadPoolExecutor):
    def __init__(self, max_workers=None, mp_context=None, initializer=None, initargs=(), max_tasks_per_child=None):
        super().__init__(max_workers=max_workers, initializer=initializer, initargs=initargs)
_cf.ProcessPoolExecutor = _ThreadPoolAsProcessPool; _cfp.ProcessPoolExecutor = _ThreadPoolAsProcessPool
