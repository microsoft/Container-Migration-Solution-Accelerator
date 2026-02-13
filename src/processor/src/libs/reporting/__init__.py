"""
Migration Reporting Module

Comprehensive failure and success reporting system for Kubernetes migration processes.
Provides structured context capture, intelligent analysis, and actionable remediation guidance.
"""

from .migration_report_generator import (
    MigrationReportCollector,
    MigrationReportGenerator,
)
from .models.failure_context import FailureContext, FailureSeverity, FailureType
from .models.migration_report import MigrationReport, ReportStatus

__all__ = [
    "MigrationReportCollector",
    "MigrationReportGenerator",
    "MigrationReport",
    "ReportStatus",
    "FailureContext",
    "FailureType",
    "FailureSeverity",
]
