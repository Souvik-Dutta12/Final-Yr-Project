"""
Celery application configuration.
Single entry point — all tasks are auto-discovered from monitoring/core/.
"""

from celery import Celery
from monitoring.config import monitoring_config

celery_app = Celery(
    "monitoring_worker",
    broker = monitoring_config.redis_url,
    backend = monitoring_config.redis_url,
    include = [
        "monitoring.core.tasks", 
        # "monitoring.alerts.tasks",
    ],
)

# Task configuration
celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Result backend settings
    result_expires=86400,       # keep results for 24 hours

    # Queues — different priorities
    task_routes={
        "monitoring.core.tasks.run_monitoring_pipeline": {"queue": "monitoring"},
        "monitoring.alerts.tasks.run_alert_generation": {"queue": "alerts"},
        "monitoring.core.tasks.ping_task": {"queue": "monitoring"},
        "monitoring.core.tasks.test_echo_task": {"queue": "monitoring"}
    },

    # Worker settings
    worker_prefetch_multiplier=1,   # one task at a time per worker (GEE is heavy)
    task_acks_late=True,            # ack only after completion → no lost tasks
    worker_max_tasks_per_child=50,  # restart worker after N tasks to free memory
   
    # Retry defaults
    task_max_retries=3,
    task_default_retry_delay=60,    # seconds before retry

    # Soft/hard time limits per task
    task_soft_time_limit=600,       # 10 min soft limit — triggers SoftTimeLimitExceeded
    task_time_limit=720,            # 12 min hard kill


    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_transport_options={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
        "max_connections": 20,
    },
    result_backend_transport_options={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
    },
    # Fail fast + loud instead of silent timeout
    broker_connection_timeout=5,
)