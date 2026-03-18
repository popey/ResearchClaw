"""Cron skill – manage scheduled jobs through the runtime API."""


def register():
    """Register cron scheduling tools."""
    from .tools import (
        cron_create_job,
        cron_delete_job,
        cron_get_job,
        cron_list_jobs,
        cron_pause_job,
        cron_resume_job,
        cron_run_job,
    )

    return {
        "cron_list_jobs": cron_list_jobs,
        "cron_get_job": cron_get_job,
        "cron_create_job": cron_create_job,
        "cron_delete_job": cron_delete_job,
        "cron_pause_job": cron_pause_job,
        "cron_resume_job": cron_resume_job,
        "cron_run_job": cron_run_job,
    }
