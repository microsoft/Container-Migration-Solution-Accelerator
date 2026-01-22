# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Prompt/template rendering utilities.

This module wraps a minimal subset of Jinja2 usage to render text prompts from
either an in-memory template string or a template file.

Operational expectations:
    - Callers pass only non-sensitive runtime values.
    - Rendering is synchronous; keep templates small to avoid blocking.
"""

# load text as a template then render with jinja2
# it should support async resource management.
from jinja2 import Template


class TemplateUtility:
    """Render Jinja2 templates from strings or files."""

    @staticmethod
    def render_from_file(file_path: str, **kwargs) -> str:
        """Render a Jinja2 template from a UTF-8 text file.

        Args:
            file_path: Path to a text file containing a Jinja2 template.
            **kwargs: Variables made available to the template during rendering.

        Returns:
            Rendered template string.
        """
        # Read the template file
        with open(file_path, "r", encoding="utf-8") as file:
            template_content = file.read()

        # Create a Jinja2 Template object
        template = Template(template_content)

        # Render the template with provided keyword arguments
        rendered_content = template.render(**kwargs)

        return rendered_content

    @staticmethod
    def render(template_str: str, **kwargs) -> str:
        """Render a Jinja2 template from an in-memory string.

        Args:
            template_str: Jinja2 template source.
            **kwargs: Variables made available to the template during rendering.

        Returns:
            Rendered template string.
        """
        # Create a Jinja2 Template object
        template = Template(template_str)

        # Render the template with provided keyword arguments
        rendered_content = template.render(**kwargs)

        return rendered_content
