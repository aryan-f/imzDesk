import logging
import os

import psutil

logger = logging.getLogger(__name__)


def memory_metrics():
    used = process_tree_rss()
    total = slurm_memory_limit() or psutil.virtual_memory().total
    usage_percent = 0.0 if total <= 0 else min(100.0, used / total * 100)
    metrics = {
        'usage_percent': round(usage_percent, 2),
        'used': round(used / (1024 ** 3), 2),
        'total': round(total / (1024 ** 3), 2),
    }
    logger.debug(
        'Collected memory metrics used_gib=%.2f total_gib=%.2f usage_percent=%.2f',
        metrics['used'],
        metrics['total'],
        metrics['usage_percent'],
    )
    return metrics


def process_tree_rss() -> int:
    process = psutil.Process()
    rss = process.memory_info().rss
    for child in process.children(recursive=True):
        try:
            rss += child.memory_info().rss
        except psutil.NoSuchProcess:
            logger.debug('Process exited while collecting memory metrics pid=%d', child.pid)
        except psutil.AccessDenied:
            logger.debug('Access denied while collecting child memory metrics pid=%d', child.pid)
    logger.debug('Collected process tree RSS bytes=%d', rss)
    return rss


def slurm_memory_limit() -> int | None:
    if value := os.environ.get('SLURM_MEM_PER_NODE'):
        limit = int(value) * 1024 ** 2
        logger.debug('Using SLURM node memory limit megabytes=%s bytes=%d', value, limit)
        return limit
    if value := os.environ.get('SLURM_MEM_PER_CPU'):
        cpus = int(os.environ.get('SLURM_CPUS_PER_TASK') or os.environ.get('SLURM_CPUS_ON_NODE') or '1')
        limit = int(value) * cpus * 1024 ** 2
        logger.debug('Using SLURM CPU memory limit megabytes_per_cpu=%s cpus=%d bytes=%d', value, cpus, limit)
        return limit
    logger.debug('No SLURM memory limit configured')
    return None
