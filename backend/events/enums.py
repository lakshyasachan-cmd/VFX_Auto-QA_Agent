"""
Enumerations for the VFX Event Subsystem.
Strictly decoupled from any AI/Agent logic.
"""

from enum import Enum


class SourceSystem(str, Enum):
    DEADLINE = "deadline"
    TRACTOR = "tractor"
    OPENCUE = "opencue"
    SHOTGRID = "shotgrid"
    FTRACK = "ftrack"
    ASSET_STORAGE = "asset_storage"
    STORAGE_MONITOR = "storage_monitor"
    GENERIC_VFX = "generic_vfx"


class EventType(str, Enum):
    RENDER_JOB_FAILED = "RENDER_JOB_FAILED"
    RENDER_JOB_COMPLETED = "RENDER_JOB_COMPLETED"
    RENDER_JOB_STARTED = "RENDER_JOB_STARTED"
    NODE_UNHEALTHY = "NODE_UNHEALTHY"
    ASSET_VALIDATION_FAILED = "ASSET_VALIDATION_FAILED"
    FRAME_CORRUPTION_DETECTED = "FRAME_CORRUPTION_DETECTED"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class EntityType(str, Enum):
    JOB = "job"
    NODE = "node"
    ASSET = "asset"
    FRAME = "frame"
    SHOT = "shot"
    SEQUENCE = "sequence"
    PROJECT = "project"
