"""
JSON Formatter for Migration Reports

Provides structured JSON output for machine processing and API consumption.
"""

import json

from ..models.migration_report import MigrationReport


class JsonReportFormatter:
    """Formats migration reports as structured JSON."""

    @staticmethod
    def format_report(report: MigrationReport, indent: int = 2) -> str:
        """
        Format a migration report as JSON string.

        Args:
            report: Migration report to format
            indent: JSON indentation level

        Returns:
            Formatted JSON string
        """
        # Convert Pydantic model to dict
        report_dict = report.model_dump()

        # Format as JSON with proper indentation
        return json.dumps(report_dict, indent=indent, default=str)

    @staticmethod
    def format_summary_json(report: MigrationReport) -> str:
        """
        Format just the executive summary as JSON for quick consumption.

        Args:
            report: Migration report to summarize

        Returns:
            JSON string with executive summary
        """
        summary_data = {
            "report_id": report.report_id,
            "process_id": report.process_id,
            "timestamp": report.timestamp_iso,
            "overall_status": report.overall_status.value,
            "completion_percentage": report.executive_summary.completion_percentage,
            "total_execution_time": report.total_execution_time_seconds,
            "critical_issues": report.executive_summary.critical_issues_count,
            "files_processed": report.executive_summary.files_processed,
            "files_failed": report.executive_summary.files_failed,
            "actionable_recommendations": report.executive_summary.actionable_recommendations_count,
        }

        return json.dumps(summary_data, indent=2)

    @staticmethod
    def save_to_file(report: MigrationReport, file_path: str) -> None:
        """
        Save migration report to JSON file.

        Args:
            report: Migration report to save
            file_path: Path where to save the JSON file
        """
        json_content = JsonReportFormatter.format_report(report)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_content)
