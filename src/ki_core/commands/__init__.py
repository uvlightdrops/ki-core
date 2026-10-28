"""Shared CLI commands for ki-core and downstream apps."""

from ki_core.commands.config import (
    run_resolve,
    run_skeleton,
    run_show,
    run_verify,
)
from ki_core.commands.doctor import run_doctor
from ki_core.commands.profile import (
    run_profile_active,
    run_profile_list,
    run_profile_set,
)
from ki_core.commands.stage import run_stage_active, run_stage_list, run_stage_set
from ki_core.commands.server_management import (
    run_server_status,
    run_server_register,
    run_server_unregister,
    run_server_detect_orphans,
    run_server_cleanup,
    run_server_sync,
    run_server_start,
    run_server_stop,
    run_server_restart,
)

__all__ = [
    "run_doctor",
    "run_resolve",
    "run_verify",
    "run_skeleton",
    "run_show",
    "run_profile_list",
    "run_profile_set",
    "run_profile_active",
    "run_stage_list",
    "run_stage_set",
    "run_stage_active",
    "run_server_status",
    "run_server_register",
    "run_server_unregister",
    "run_server_detect_orphans",
    "run_server_cleanup",
    "run_server_sync",
    "run_server_start",
    "run_server_stop",
    "run_server_restart",
]
