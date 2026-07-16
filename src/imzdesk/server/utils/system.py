import logging
import os

import psutil

logger = logging.getLogger(__name__)


def memory_metrics():
    used = process_tree_rss()
    total = slurm_memory_limit() or psutil.virtual_memory().total
    usage_percent = 0.0 if total <= 0 else min(100.0, used / total * 100)
    return {
        'usage_percent': round(usage_percent, 2),
        'used': round(used / (1024 ** 3), 2),
        'total': round(total / (1024 ** 3), 2),
    }


def process_tree_rss() -> int:
    process = psutil.Process()
    rss = process.memory_info().rss
    for child in process.children(recursive=True):
        try:
            rss += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return rss


def slurm_memory_limit() -> int | None:
    if value := os.environ.get('SLURM_MEM_PER_NODE'):
        return int(value) * 1024 ** 2
    if value := os.environ.get('SLURM_MEM_PER_CPU'):
        cpus = int(os.environ.get('SLURM_CPUS_PER_TASK') or os.environ.get('SLURM_CPUS_ON_NODE') or '1')
        return int(value) * cpus * 1024 ** 2
    return None
