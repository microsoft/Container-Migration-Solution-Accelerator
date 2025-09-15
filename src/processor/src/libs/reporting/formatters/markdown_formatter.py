"""
Markdown Formatter for Migration Reports

Provides human-readable markdown output for documentation and stakeholder communication.
"""

from ..models.migration_report import MigrationReport, ReportStatus


class MarkdownReportFormatter:
    """Formats migration reports as human-readable markdown."""

    @staticmethod
    def format_report(report: MigrationReport) -> str:
        """
        Format a complete migration report as markdown.

        Args:
            report: Migration report to format

        Returns:
            Formatted markdown string
        """
        sections = []

        # Header
        sections.append(MarkdownReportFormatter._format_header(report))

        # Executive Summary
        sections.append(MarkdownReportFormatter._format_executive_summary(report))

        # Step Details
        sections.append(MarkdownReportFormatter._format_step_details(report))

        # Failure Analysis (if applicable)
        if report.failure_analysis:
            sections.append(MarkdownReportFormatter._format_failure_analysis(report))

        # Remediation Guide (if applicable)
        if report.remediation_guide:
            sections.append(MarkdownReportFormatter._format_remediation_guide(report))

        # Supporting Data
        sections.append(MarkdownReportFormatter._format_supporting_data(report))

        return "\n\n".join(sections)

    @staticmethod
    def format_executive_summary(report: MigrationReport) -> str:
        """
        Format just the executive summary for quick stakeholder communication.

        Args:
            report: Migration report to summarize

        Returns:
            Markdown executive summary
        """
        sections = [
            MarkdownReportFormatter._format_header(report),
            MarkdownReportFormatter._format_executive_summary(report),
        ]

        if report.remediation_guide and report.remediation_guide.priority_actions:
            sections.append("## Immediate Actions Required\n")
            for i, action in enumerate(
                report.remediation_guide.priority_actions[:3], 1
            ):
                sections.append(f"{i}. **{action.title}**: {action.description}")

        return "\n\n".join(sections)

    @staticmethod
    def _format_header(report: MigrationReport) -> str:
        """Format the report header."""
        status_emoji = {
            ReportStatus.SUCCESS: "✅",
            ReportStatus.PARTIAL_SUCCESS: "⚠️",
            ReportStatus.FAILED: "❌",
            ReportStatus.TIMEOUT: "⏱️",
            ReportStatus.CANCELLED: "🛑",
        }

        emoji = status_emoji.get(report.overall_status, "❓")

        return f"""# Migration Report {emoji}

**Process ID**: `{report.process_id}`
**Report ID**: `{report.report_id}`
**Status**: {report.overall_status.value.upper()}
**Generated**: {report.timestamp_iso}
**Execution Time**: {report.total_execution_time_seconds:.1f}s"""

    @staticmethod
    def _format_executive_summary(report: MigrationReport) -> str:
        """Format the executive summary section."""
        summary = report.executive_summary

        progress_bar = "█" * int(summary.completion_percentage / 10) + "░" * (
            10 - int(summary.completion_percentage / 10)
        )

        content = f"""## Executive Summary

**Progress**: {summary.completion_percentage:.1f}% {progress_bar}

### Key Metrics
- **Files Processed**: {summary.files_processed} / {summary.total_files}
- **Files Failed**: {summary.files_failed}
- **Critical Issues**: {summary.critical_issues_count}
- **Actionable Recommendations**: {summary.actionable_recommendations_count}"""

        if summary.completed_steps:
            content += f"\n- **Completed Steps**: {', '.join(summary.completed_steps)}"

        if summary.failed_step:
            content += f"\n- **Failed Step**: {summary.failed_step}"

        if summary.estimated_fix_time:
            content += f"\n- **Estimated Fix Time**: {summary.estimated_fix_time}"

        return content

    @staticmethod
    def _format_step_details(report: MigrationReport) -> str:
        """Format the step details section."""
        if not report.step_details:
            return "## Step Details\n\nNo step details available."

        content = ["## Step Details\n"]

        for step in report.step_details:
            status_emoji = {
                "completed": "✅",
                "failed": "❌",
                "partial": "⚠️",
                "skipped": "⏭️",
            }

            emoji = status_emoji.get(step.status, "❓")
            time_info = (
                f" ({step.execution_time_seconds:.1f}s)"
                if step.execution_time_seconds
                else ""
            )

            content.append(f"### {step.step_name.title()} Step {emoji}{time_info}")
            content.append(f"**Status**: {step.status}")

            if step.files_processed:
                content.append(f"**Files Processed**: {len(step.files_processed)}")

            if step.files_failed:
                content.append(f"**Files Failed**: {', '.join(step.files_failed)}")

            if step.failure_contexts:
                content.append("**Failures**:")
                for failure in step.failure_contexts:
                    content.append(
                        f"- {failure.severity.value.upper()}: {failure.error_message}"
                    )

            if step.warnings:
                content.append("**Warnings**:")
                for warning in step.warnings:
                    content.append(f"- {warning}")

        return "\n".join(content)

    @staticmethod
    def _format_failure_analysis(report: MigrationReport) -> str:
        """Format the failure analysis section."""
        analysis = report.failure_analysis
        if not analysis:
            return ""

        content = ["## Failure Analysis\n"]

        if analysis.root_cause:
            content.append(f"**Root Cause**: {analysis.root_cause}")

        if analysis.contributing_factors:
            content.append("**Contributing Factors**:")
            for factor in analysis.contributing_factors:
                content.append(f"- {factor}")

        if analysis.failure_pattern:
            content.append(f"**Failure Pattern**: {analysis.failure_pattern}")

        if analysis.recurrence_likelihood:
            likelihood_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
            emoji = likelihood_emoji.get(analysis.recurrence_likelihood, "❓")
            content.append(
                f"**Recurrence Likelihood**: {analysis.recurrence_likelihood} {emoji}"
            )

        return "\n".join(content)

    @staticmethod
    def _format_remediation_guide(report: MigrationReport) -> str:
        """Format the remediation guide section."""
        guide = report.remediation_guide
        if not guide:
            return ""

        content = ["## Remediation Guide\n"]

        if guide.priority_actions:
            content.append("### Priority Actions")
            for i, action in enumerate(guide.priority_actions, 1):
                content.append(f"{i}. **{action.title}**")
                content.append(f"   {action.description}")
                if action.estimated_effort:
                    content.append(f"   *Estimated effort: {action.estimated_effort}*")
                if action.commands:
                    content.append("   Commands:")
                    for cmd in action.commands:
                        content.append(f"   ```bash\n   {cmd}\n   ```")

        if guide.configuration_recommendations:
            content.append("\n### Configuration Recommendations")
            for i, rec in enumerate(guide.configuration_recommendations, 1):
                content.append(f"{i}. **{rec.title}**: {rec.description}")

        if guide.when_to_retry:
            content.append(f"\n### When to Retry\n{guide.when_to_retry}")

        return "\n".join(content)

    @staticmethod
    def _format_supporting_data(report: MigrationReport) -> str:
        """Format the supporting data section."""
        data = report.supporting_data
        content = ["## Supporting Information\n"]

        if data.environment_info:
            content.append("### Environment")
            for key, value in data.environment_info.items():
                content.append(f"- **{key.replace('_', ' ').title()}**: {value}")

        if data.dependency_versions:
            content.append("\n### Dependencies")
            for dep, version in data.dependency_versions.items():
                content.append(f"- {dep}: {version}")

        if data.log_excerpts:
            content.append("\n### Recent Log Entries")
            for log_entry in data.log_excerpts[-5:]:  # Last 5 entries
                timestamp = log_entry.get("timestamp", "Unknown")
                level = log_entry.get("level", "INFO")
                message = log_entry.get("message", "")
                content.append(f"- `{timestamp}` [{level}] {message}")

        return "\n".join(content)

    @staticmethod
    def save_to_file(report: MigrationReport, file_path: str) -> None:
        """
        Save migration report to markdown file.

        Args:
            report: Migration report to save
            file_path: Path where to save the markdown file
        """
        markdown_content = MarkdownReportFormatter.format_report(report)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
