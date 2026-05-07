import re

from arq import cron
from arq.connections import RedisSettings

from outreach.config import get_settings
from outreach.tasks.check_replies import task_check_replies
from outreach.tasks.classify import task_classify
from outreach.tasks.discover import task_discover
from outreach.tasks.harvest import task_harvest
from outreach.tasks.send import task_send


def _get_redis_settings() -> RedisSettings:
    settings = get_settings()
    m = re.match(r"redis://([^:/]+)(?::(\d+))?", settings.redis_url)
    host = m.group(1) if m else "localhost"
    port = int(m.group(2)) if m and m.group(2) else 6379
    return RedisSettings(host=host, port=port)


class WorkerSettings:
    functions = [
        task_discover,
        task_harvest,
        task_classify,
        task_send,
        task_check_replies,
    ]
    redis_settings = _get_redis_settings()
    cron_jobs = [
        cron(task_discover, hour=6),
        cron(task_harvest, hour=7),
        cron(task_classify, hour=8),
        cron(task_send, hour=10),
        cron(task_check_replies, minute={0}),
    ]
