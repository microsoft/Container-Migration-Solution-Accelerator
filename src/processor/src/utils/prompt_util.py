# load text as a template then render with jinja2
# it should support async resource management.
from jinja2 import Template

class TemplateUtility:
    @staticmethod
    def render_from_file(file_path: str, **kwargs) -> str:
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
        # Create a Jinja2 Template object
        template = Template(template_str)

        # Render the template with provided keyword arguments
        rendered_content = template.render(**kwargs)

        return rendered_content
