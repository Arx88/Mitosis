# Placeholder for the new tool code from the issue description
import os
import json
import logging
import tempfile
import asyncio
from typing import Dict, Any, List, Optional, Union # Ensure Optional is imported
from datetime import datetime

from sandbox.tool_base import SandboxToolsBase
from agentpress.thread_manager import ThreadManager
from agentpress.tool import ToolResult, openapi_schema # Removed Tool as it's not directly used for class inheritance here
import os
import json
import logging
import tempfile
import asyncio # Keep for subprocess if sandbox.run_command is not sufficient for all cases or for internal async ops
from typing import Dict, Any, List, Optional, Union # Ensure Optional is imported
from datetime import datetime

logger = logging.getLogger(__name__)

class SandboxDocumentGenerationTool(SandboxToolsBase):

    # NOTE: project_id, thread_manager (and thread_id if applicable) are Optional to allow default instantiation.
    def __init__(self, project_id: Optional[str] = None, thread_manager: Optional[ThreadManager] = None):
        # super().__init__ can handle Optional project_id/thread_manager.
        super().__init__(project_id, thread_manager)
        # self.workspace_path should be inherited from SandboxToolsBase
        # Ensure workspace_path is available from SandboxToolsBase, otherwise this will fail
        if not hasattr(self, 'workspace_path') or not self.workspace_path:
            # Fallback or error, this indicates an issue with SandboxToolsBase or its initialization
            logger.warning("workspace_path not found in SandboxToolsBase, using a default.")
            # This default might not be correct depending on where SandboxToolsBase is defined/how it works
            self.workspace_path = f"/mnt/sandbox_workspace" # A more common sandbox path

        self.templates_dir = f"{self.workspace_path}/templates"
        self.documents_dir = f"{self.workspace_path}/documents"
        # Directory creation will be handled by _ensure_dirs

    async def _ensure_dirs(self):
        await self._ensure_sandbox() # Ensure sandbox is available
        if not hasattr(self, '_dirs_initialized'):
            for directory in [self.templates_dir, self.documents_dir]:
                logger.info(f"Ensuring directory in sandbox: {directory}")
                # Use run_command to create directories inside the sandbox
                # The path used here must be the path *inside* the sandbox
                result = await self.sandbox.run_command(f"mkdir -p {directory}")
                if result.exit_code != 0:
                    logger.error(f"Failed to create directory {directory} in sandbox: {result.stderr}")
                    # Depending on strictness, might raise an error or just log
                    # For now, let's log and continue, assuming some paths might exist or be read-only
            self._dirs_initialized = True

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "markdown_to_pdf",
            "description": "Converts a Markdown file (located in the sandbox) to PDF (saved in the sandbox) with advanced formatting options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "markdown_file_sandbox_path": {"type": "string", "description": "Absolute path to the source Markdown file within the sandbox."},
                    "output_file_sandbox_path": {"type": "string", "description": "Absolute path within the sandbox to save the generated PDF file."},
                    "title": {"type": "string", "description": "(Optional) Title of the document."},
                    "author": {"type": "string", "description": "(Optional) Author of the document."},
                    "css_file_sandbox_path": {"type": "string", "description": "(Optional) Absolute path to a custom CSS file within the sandbox."},
                    "page_size": {"type": "string", "description": "(Opcional) Page size. Options: 'A4', 'Letter', 'Legal'. Default is 'A4'."},
                    "include_toc": {"type": "boolean", "description": "(Opcional) Whether to include a table of contents. Default is true."},
                    "include_header": {"type": "boolean", "description": "(Opcional) Whether to include a header. Default is true."},
                    "include_footer": {"type": "boolean", "description": "(Opcional) Whether to include a footer. Default is true."}
                },
                "required": ["markdown_file_sandbox_path", "output_file_sandbox_path"]
            }
        }
    })
    async def markdown_to_pdf(self, markdown_file_sandbox_path: str, output_file_sandbox_path: str, title: Optional[str] = None, author: Optional[str] = None, css_file_sandbox_path: Optional[str] = None, page_size: str = "A4", include_toc: bool = True, include_header: bool = True, include_footer: bool = True) -> ToolResult:
        await self._ensure_dirs()
        logger.info(f"Converting Markdown {markdown_file_sandbox_path} to PDF {output_file_sandbox_path} in sandbox")

        if not await self.sandbox.file_exists(markdown_file_sandbox_path):
            return self.fail_response(f"Markdown file {markdown_file_sandbox_path} not found in sandbox.")
        if css_file_sandbox_path and not await self.sandbox.file_exists(css_file_sandbox_path):
            return self.fail_response(f"CSS file {css_file_sandbox_path} not found in sandbox.")

        # Using `manus-md-to-pdf` as specified in original placeholder
        # This tool and its dependencies (like WeasyPrint, pandoc) must be installed in the sandbox environment.
        cmd_parts = [
            "manus-md-to-pdf", # Ensure this command is available in the sandbox PATH
            f'"{markdown_file_sandbox_path}"', # Quote paths
            f'"{output_file_sandbox_path}"'
        ]
        if title: cmd_parts.append(f'--title "{title}"')
        if author: cmd_parts.append(f'--author "{author}"')
        if css_file_sandbox_path: cmd_parts.append(f'--css "{css_file_sandbox_path}"')
        if page_size: cmd_parts.append(f'--page-size {page_size}')
        if include_toc: cmd_parts.append('--include-toc')
        if include_header: cmd_parts.append('--include-header')
        if include_footer: cmd_parts.append('--include-footer')

        command = " ".join(cmd_parts)
        logger.info(f"Executing command in sandbox: {command}")

        process_output = await self.sandbox.run_command(command, timeout=120)

        if process_output.exit_code == 0:
            if await self.sandbox.file_exists(output_file_sandbox_path):
                # Return the sandbox path; the caller (agent) can decide to download it.
                return self.success_response({"output_file_sandbox_path": output_file_sandbox_path, "message": "PDF generated successfully in sandbox."})
            else:
                return self.fail_response(f"PDF generation command succeeded but output file {output_file_sandbox_path} not found in sandbox. STDOUT: {process_output.stdout} STDERR: {process_output.stderr}")
        else:
            return self.fail_response(f"Failed to convert Markdown to PDF. Exit code: {process_output.exit_code}. Error: {process_output.stderr}. STDOUT: {process_output.stdout}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "create_document_template",
            "description": "Creates a new document template (e.g., Markdown, HTML) in the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_name": {"type": "string", "description": "Name for the template (e.g., 'invoice_template'). Extension will be added based on type."},
                    "content": {"type": "string", "description": "The content of the template."},
                    "template_type": {"type": "string", "description": "Type of the template (e.g., 'markdown', 'html'). Default is 'markdown'."}
                },
                "required": ["template_name", "content"]
            }
        }
    })
    async def create_document_template(self, template_name: str, content: str, template_type: str = "markdown") -> ToolResult:
        await self._ensure_dirs()
        # Sanitize template_name to prevent path traversal or invalid characters
        safe_template_name = "".join(c for c in template_name if c.isalnum() or c in ('_', '-')).rstrip()
        if not safe_template_name:
            return self.fail_response("Invalid template name provided.")

        template_filename = f"{safe_template_name}.{template_type}"
        template_sandbox_path = f"{self.templates_dir}/{template_filename}"

        logger.info(f"Creating template {template_sandbox_path} of type {template_type} in sandbox")

        # Use a temporary file on the agent host to upload content to the sandbox
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=f".{template_type}") as tmp_file:
                tmp_file.write(content)
                host_temp_path = tmp_file.name

            await self.sandbox.upload_file(host_temp_path, template_sandbox_path)
            os.remove(host_temp_path) # Clean up temp file on host

            if await self.sandbox.file_exists(template_sandbox_path):
                return self.success_response({"template_sandbox_path": template_sandbox_path, "message": "Template created successfully in sandbox."})
            else:
                return self.fail_response(f"Failed to create template file {template_sandbox_path} in sandbox after upload.")
        except Exception as e:
            logger.exception(f"Error creating document template {template_name}: {e}")
            return self.fail_response(f"Error creating document template: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "list_templates",
            "description": "Lists available document templates from the sandbox templates directory.",
            "parameters": {"type": "object", "properties": {}}
        }
    })
    async def list_templates(self) -> ToolResult:
        await self._ensure_dirs()
        logger.info(f"Listing templates from sandbox directory: {self.templates_dir}")

        # Ensure the path is just the directory name for listing
        # The actual listing behavior depends on SandboxToolsBase or underlying sandbox implementation
        # Assuming run_command with 'ls' is a reliable way if no direct fs.list_files.
        list_command = f"ls -p {self.templates_dir} | grep -v /" # List files, not directories

        process_output = await self.sandbox.run_command(list_command)

        if process_output.exit_code == 0:
            template_files = [f.strip() for f in process_output.stdout.splitlines() if f.strip()]
            templates_info = []
            for fname in template_files:
                # Basic parsing, could be enhanced if more metadata was stored/needed
                name_part, ext_part = os.path.splitext(fname)
                templates_info.append({
                    "name": name_part,
                    "type": ext_part.lstrip('.'),
                    "sandbox_path": f"{self.templates_dir}/{fname}"
                })
            return self.success_response({"templates": templates_info})
        else:
            # If ls fails (e.g. dir not found, or empty and ls returns error), return empty list or error
            logger.warning(f"Could not list templates from {self.templates_dir}. Error: {process_output.stderr}")
            # It's common for `ls` to return non-zero if dir is empty but exists.
            # Check if directory exists if ls fails
            # This check itself is tricky. For now, assume empty list on error if not critical.
            return self.success_response({"templates": [], "message": f"No templates found or error listing from {self.templates_dir}. Details: {process_output.stderr}"})


    @openapi_schema({
        "type": "function",
        "function": {
            "name": "generate_document_from_template",
            "description": "Generates a new document from an existing template and context data. (Templating engine like Jinja2 must be available in sandbox).",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_sandbox_path": {"type": "string", "description": "Absolute path to the template file within the sandbox (e.g., from list_templates)."},
                    "output_file_sandbox_path": {"type": "string", "description": "Absolute path in the sandbox to save the generated document."},
                    "context_json_string": {"type": "string", "description": "JSON string representing the context data to fill into the template."},
                    # output_format might be redundant if template implies it, or useful if conversion is also part of this.
                    # For now, assume the template itself defines the primary output type.
                },
                "required": ["template_sandbox_path", "output_file_sandbox_path", "context_json_string"]
            }
        }
    })
    async def generate_document_from_template(self, template_sandbox_path: str, output_file_sandbox_path: str, context_json_string: str) -> ToolResult:
        await self._ensure_dirs()
        logger.info(f"Generating document {output_file_sandbox_path} from template {template_sandbox_path} in sandbox")

        if not await self.sandbox.file_exists(template_sandbox_path):
            return self.fail_response(f"Template file {template_sandbox_path} not found in sandbox.")

        try:
            # The context is provided as a JSON string.
            # A Python script will be run in the sandbox to perform the rendering.
            # This avoids needing complex data transfer for the context dictionary itself if it were large.
            # Create a temporary file for the context data on the host
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=".json") as tmp_context_file:
                tmp_context_file.write(context_json_string)
                host_context_path = tmp_context_file.name

            sandbox_context_path = f"{self.workspace_path}/_temp_context_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.json"
            await self.sandbox.upload_file(host_context_path, sandbox_context_path)
            os.remove(host_context_path)

            # Python script to run in sandbox for Jinja2 rendering
            render_script_content = f"""
import json
import sys
from jinja2 import Environment, FileSystemLoader, select_autoescape

try:
    template_dir = "{os.path.dirname(template_sandbox_path)}"
    template_file = "{os.path.basename(template_sandbox_path)}"
    context_file_path = "{sandbox_context_path}"
    output_file_path = "{output_file_sandbox_path}"

    with open(context_file_path, 'r', encoding='utf-8') as f:
        context_data = json.load(f)

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml', 'md', 'txt']) # Adjust as needed
    )
    template = env.get_template(template_file)
    rendered_content = template.render(context_data)

    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(rendered_content)

    print(f"Document generated successfully at {{output_file_path}}")
    sys.exit(0)
except Exception as e:
    print(f"Error during template rendering: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
            """
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=".py") as tmp_script_file:
                tmp_script_file.write(render_script_content)
                host_script_path = tmp_script_file.name

            sandbox_script_path = f"{self.workspace_path}/_render_script_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.py"
            await self.sandbox.upload_file(host_script_path, sandbox_script_path)
            os.remove(host_script_path)

            # Command to execute the rendering script in the sandbox
            # Ensure jinja2 is installed in the sandbox: python -m pip install Jinja2
            render_command = f"python {sandbox_script_path}"
            logger.info(f"Executing render script in sandbox: {render_command}")
            process_output = await self.sandbox.run_command(render_command, timeout=60)

            # Clean up temporary files in sandbox
            await self.sandbox.run_command(f"rm {sandbox_context_path} {sandbox_script_path}")

            if process_output.exit_code == 0:
                if await self.sandbox.file_exists(output_file_sandbox_path):
                    return self.success_response({"output_file_sandbox_path": output_file_sandbox_path, "message": "Document generated successfully from template in sandbox."})
                else:
                     return self.fail_response(f"Render script succeeded but output file {output_file_sandbox_path} not found. STDOUT: {process_output.stdout} STDERR: {process_output.stderr}")
            else:
                return self.fail_response(f"Failed to generate document from template. Error: {process_output.stderr}. STDOUT: {process_output.stdout}")

        except json.JSONDecodeError:
            return self.fail_response("Invalid JSON string provided for context.")
        except Exception as e:
            logger.exception(f"Error generating document from template: {e}")
            return self.fail_response(f"Error generating document from template: {str(e)}")


    @openapi_schema({
        "type": "function",
        "function": {
            "name": "convert_document",
            "description": "Converts a document from one format to another using Pandoc or WeasyPrint (must be installed in sandbox).",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_file_sandbox_path": {"type": "string", "description": "Absolute path to the source document file within the sandbox."},
                    "output_file_sandbox_path": {"type": "string", "description": "Absolute path in the sandbox to save the converted document."},
                    "output_format": {"type": "string", "description": "Desired output format (e.g., 'pdf', 'docx', 'html', 'md')."},
                    "input_format": {"type": "string", "description": "(Optional) Input format, if it cannot be inferred by Pandoc."}
                },
                "required": ["input_file_sandbox_path", "output_file_sandbox_path", "output_format"]
            }
        }
    })
    async def convert_document(self, input_file_sandbox_path: str, output_file_sandbox_path: str, output_format: str, input_format: Optional[str] = None) -> ToolResult:
        await self._ensure_dirs() # Ensures documents_dir might be used if output path is relative
        logger.info(f"Converting {input_file_sandbox_path} to {output_file_sandbox_path} (format: {output_format}) in sandbox")

        if not await self.sandbox.file_exists(input_file_sandbox_path):
            return self.fail_response(f"Input file {input_file_sandbox_path} not found in sandbox.")

        # Determine tool based on output format, Pandoc is more versatile
        # WeasyPrint is good for HTML/CSS to PDF/PNG.
        # Assuming Pandoc is the primary tool here unless specific conditions met.
        # Example: if input is HTML and output is PDF, WeasyPrint might be an option.
        # For simplicity, let's default to Pandoc. Ensure it's installed in the sandbox.

        cmd_parts = ["pandoc", f'"{input_file_sandbox_path}"', "-o", f'"{output_file_sandbox_path}"']
        if input_format:
            cmd_parts.extend(["-f", input_format])
        if output_format: # Pandoc usually infers from output filename, but explicit is safer
            cmd_parts.extend(["-t", output_format])

        # Add common Pandoc flags for quality if needed, e.g. --pdf-engine for PDF
        if output_format == "pdf":
            cmd_parts.append("--pdf-engine=weasyprint") # Example, or could be pdflatex, etc.
                                                        # Requires the engine to be installed.

        command = " ".join(cmd_parts)
        logger.info(f"Executing Pandoc command in sandbox: {command}")
        process_output = await self.sandbox.run_command(command, timeout=120)

        if process_output.exit_code == 0:
            if await self.sandbox.file_exists(output_file_sandbox_path):
                return self.success_response({"output_file_sandbox_path": output_file_sandbox_path, "message": "Document converted successfully in sandbox."})
            else:
                return self.fail_response(f"Pandoc command succeeded but output file {output_file_sandbox_path} not found. STDOUT: {process_output.stdout} STDERR: {process_output.stderr}")

        else:
            # Fallback or specific handling for WeasyPrint if Pandoc fails or for HTML->PDF
            if (input_format == "html" or input_file_sandbox_path.endswith(".html")) and output_format == "pdf":
                logger.info("Pandoc failed or specific case for HTML->PDF, trying WeasyPrint.")
                # Ensure WeasyPrint is installed: python -m pip install weasyprint
                wp_command = f"python -m weasyprint \"{input_file_sandbox_path}\" \"{output_file_sandbox_path}\""
                logger.info(f"Executing WeasyPrint command in sandbox: {wp_command}")
                wp_process_output = await self.sandbox.run_command(wp_command, timeout=120)

                if wp_process_output.exit_code == 0:
                    if await self.sandbox.file_exists(output_file_sandbox_path):
                         return self.success_response({"output_file_sandbox_path": output_file_sandbox_path, "message": "Document converted successfully using WeasyPrint in sandbox."})
                    else:
                        return self.fail_response(f"WeasyPrint command succeeded but output file {output_file_sandbox_path} not found. STDOUT: {wp_process_output.stdout} STDERR: {wp_process_output.stderr}")
                else:
                    return self.fail_response(f"WeasyPrint conversion failed. Exit code: {wp_process_output.exit_code}. Error: {wp_process_output.stderr}. Original Pandoc error: {process_output.stderr}")

            return self.fail_response(f"Pandoc conversion failed. Exit code: {process_output.exit_code}. Error: {process_output.stderr}. STDOUT: {process_output.stdout}")


    @openapi_schema({
        "type": "function",
        "function": {
            "name": "create_report",
            "description": "Creates a complex report by fetching data, generating content (e.g., Markdown), and converting to a specified format (e.g., PDF).",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_source_urls_json_string": {"type": "string", "description": "JSON string of a list of URLs to fetch data from (e.g., APIs)."},
                    "report_title": {"type": "string", "description": "Title for the report."},
                    "output_file_sandbox_path": {"type": "string", "description": "Absolute path in the sandbox to save the final report."},
                    "report_type": {"type": "string", "description": "Type of report (e.g., 'summary', 'detailed_analysis'). This influences content generation. Default 'summary'."},
                    "output_format": {"type": "string", "description": "Desired output format for the report (e.g., 'pdf', 'md', 'html'). Default 'pdf'."}
                },
                "required": ["data_source_urls_json_string", "report_title", "output_file_sandbox_path"]
            }
        }
    })
    async def create_report(self, data_source_urls_json_string: str, report_title: str, output_file_sandbox_path: str, report_type: str = "summary", output_format: str = "pdf") -> ToolResult:
        await self._ensure_dirs()
        logger.info(f"Creating report '{report_title}' at {output_file_sandbox_path} (format: {output_format}) in sandbox")

        try:
            data_sources = json.loads(data_source_urls_json_string)
            if not isinstance(data_sources, list):
                return self.fail_response("data_source_urls_json_string must be a JSON array of URLs.")
        except json.JSONDecodeError:
            return self.fail_response("Invalid JSON string for data_source_urls_json_string.")

        # Placeholder for actual data fetching and content generation logic
        # This would involve:
        # 1. Iterating through data_sources, fetching data (possibly using httpx or another tool via agent).
        #    For simplicity, we'll assume this step results in some text or Markdown content.
        #    This part is complex and might involve other tools or a more sophisticated agent loop.
        #    Let's simulate fetched data.

        simulated_fetched_data_content = f"# Report: {report_title}\n\nReport Type: {report_type}\nDate: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        for i, url in enumerate(data_sources):
            simulated_fetched_data_content += f"## Data from {url}\n\n(Simulated content for source {i+1})\n\nLorem ipsum dolor sit amet...\n\n"

        # Save this generated Markdown content to a temporary file in the sandbox
        temp_markdown_sandbox_path = f"{self.documents_dir}/_temp_report_content_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.md"

        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=".md") as tmp_md_file:
                tmp_md_file.write(simulated_fetched_data_content)
                host_temp_md_path = tmp_md_file.name

            await self.sandbox.upload_file(host_temp_md_path, temp_markdown_sandbox_path)
            os.remove(host_temp_md_path)
        except Exception as e:
            logger.exception(f"Error creating temporary markdown for report: {e}")
            return self.fail_response(f"Failed to stage report content in sandbox: {str(e)}")

        # Now, convert this Markdown file to the desired output_format
        if output_format.lower() == "md" or output_format.lower() == "markdown":
            # If output is Markdown, just rename/move the temp file
            # This assumes output_file_sandbox_path is different from temp_markdown_sandbox_path
            # Or, if they can be the same, the upload above could have used output_file_sandbox_path directly.
            # For clarity, let's assume we "copy" it.
            # await self.sandbox.run_command(f"cp {temp_markdown_sandbox_path} {output_file_sandbox_path}")
            # Better: if format is md, the temp file *is* the output file (adjust path above)
            # For this example, let's assume the initial temp file was the target if format is md.
            # If temp_markdown_sandbox_path was correctly named output_file_sandbox_path:
            if temp_markdown_sandbox_path == output_file_sandbox_path: # This would be true if logic was slightly different
                 if await self.sandbox.file_exists(output_file_sandbox_path):
                    await self.sandbox.run_command(f"rm {temp_markdown_sandbox_path}", timeout=10) # clean if it was not the target
                    return self.success_response({"output_file_sandbox_path": output_file_sandbox_path, "message": "Report (Markdown) created successfully."})
                 else: # Should not happen if upload was ok
                    return self.fail_response("Failed to create Markdown report (file missing).")

            # If it must be a distinct operation:
            # Re-write the temp file to the final md path if different
            # This is a bit clunky, ideally the temp file is the final if format is md.
            # Let's assume for this example, if output is MD, we use the convert function to "convert" md to md (effectively a copy)
            # This simplifies the logic flow at the cost of a slight inefficiency.
            pass # Fall through to convert_document logic below which handles md->md as a copy

        # Use convert_document for PDF, HTML, DOCX etc.
        conversion_result = await self.convert_document(
            input_file_sandbox_path=temp_markdown_sandbox_path,
            output_file_sandbox_path=output_file_sandbox_path,
            output_format=output_format,
            input_format="md" # Explicitly state input is markdown
        )

        # Clean up the temporary markdown file
        await self.sandbox.run_command(f"rm {temp_markdown_sandbox_path}", timeout=10)

        if not conversion_result.error_message: # Check if conversion was successful
             return self.success_response({
                "output_file_sandbox_path": output_file_sandbox_path, # from conversion_result.output
                "message": f"Report '{report_title}' created successfully as {output_format}."
            })
        else:
            return self.fail_response(f"Failed to create report. Content generation was okay, but final conversion to {output_format} failed: {conversion_result.error_message}")


# Example test (will also need refactoring based on SandboxToolsBase and actual sandbox interaction)
async def main_test():
    logging.basicConfig(level=logging.INFO)

    # Mock ThreadManager for testing
    class MockThreadManager:
        pass # Add any methods/props ThreadManager is expected to have if used by the tool beyond __init__

    # This needs to be a mock that accurately reflects SandboxToolsBase's capabilities,
    # especially self.sandbox and self.sandbox.run_command, self.sandbox.file_exists, self.sandbox.upload_file
    # For now, the SandboxDocumentGenerationTool inherits a mocked version from the placeholder.
    # A more realistic test would involve a TestSandboxToolsBase or patching.

    tool = SandboxDocumentGenerationTool(project_id="test_project_refactored", thread_manager=MockThreadManager())

    # --- Setup for tests: Create dummy files in the "sandbox" (mocked) ---
    # In a real test, you would use tool.sandbox.upload_file if files come from host.
    # Since _ensure_dirs uses run_command, it should work with the mocked run_command.
    # For file content, we'd need to upload. Let's assume some files are pre-existing for some tests.

    test_md_content = "# Test Markdown\n\nThis is a test."
    test_md_sandbox_path = f"{tool.documents_dir}/test_doc.md"
    test_css_sandbox_path = f"{tool.documents_dir}/test_style.css"

    # Simulate uploading test markdown and css
    # This is a simplified way for testing; actual upload would be:
    # with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp: tmp.write(test_md_content); await tool.sandbox.upload_file(tmp.name, test_md_sandbox_path)
    await tool._ensure_dirs() # Call it manually for test setup if methods don't always.
    await tool.sandbox.run_command(f"echo '{test_md_content}' > {test_md_sandbox_path}")
    await tool.sandbox.run_command(f"echo 'body {{ font-size: 12pt; }}' > {test_css_sandbox_path}")


    logger.info("--- Test: markdown_to_pdf ---")
    pdf_result = await tool.markdown_to_pdf(
        markdown_file_sandbox_path=test_md_sandbox_path,
        output_file_sandbox_path=f"{tool.documents_dir}/test_output.pdf",
        title="My Test PDF",
        css_file_sandbox_path=test_css_sandbox_path
    )
    logger.info(f"PDF Result: {pdf_result.output or pdf_result.error_message}")
    assert pdf_result.output is not None and "test_output.pdf" in pdf_result.output.get("output_file_sandbox_path","")

    logger.info("--- Test: create_document_template ---")
    template_result = await tool.create_document_template("cv_template", "Name: {{ name }}, Role: {{ role }}", "md")
    logger.info(f"Create Template Result: {template_result.output or template_result.error_message}")
    assert template_result.output is not None and "cv_template.md" in template_result.output.get("template_sandbox_path","")
    created_template_path = template_result.output.get("template_sandbox_path") if template_result.output else None

    logger.info("--- Test: list_templates ---")
    templates_list_result = await tool.list_templates()
    logger.info(f"List Templates Result: {templates_list_result.output or templates_list_result.error_message}")
    assert templates_list_result.output is not None and isinstance(templates_list_result.output.get("templates"), list)
    # Check if our created template is listed (name check might need adjustment based on ls output parsing)
    assert any(t['name'] == 'cv_template' for t in templates_list_result.output.get("templates",[]))


    logger.info("--- Test: generate_document_from_template ---")
    if created_template_path:
        context_data_json = json.dumps({"name": "Jane Doe", "role": "Software Engineer"})
        doc_gen_result = await tool.generate_document_from_template(
            template_sandbox_path=created_template_path,
            output_file_sandbox_path=f"{tool.documents_dir}/cv_jane_doe.md",
            context_json_string=context_data_json
        )
        logger.info(f"Generate Document Result: {doc_gen_result.output or doc_gen_result.error_message}")
        assert doc_gen_result.output is not None and "cv_jane_doe.md" in doc_gen_result.output.get("output_file_sandbox_path","")
    else:
        logger.warning("Skipping generate_document_from_template test as template creation failed or path not found.")

    logger.info("--- Test: convert_document (MD to HTML) ---")
    # Use the generated cv_jane_doe.md as input if available
    input_for_convert = f"{tool.documents_dir}/cv_jane_doe.md"
    if not (doc_gen_result.output and await tool.sandbox.file_exists(input_for_convert)):
        logger.info(f"Input for convert {input_for_convert} not found, using fallback {test_md_sandbox_path}")
        input_for_convert = test_md_sandbox_path # Fallback to original test_doc.md

    convert_result_html = await tool.convert_document(
        input_file_sandbox_path=input_for_convert,
        output_file_sandbox_path=f"{tool.documents_dir}/converted_doc.html",
        output_format="html",
        input_format="md"
    )
    logger.info(f"Convert MD to HTML Result: {convert_result_html.output or convert_result_html.error_message}")
    assert convert_result_html.output is not None and "converted_doc.html" in convert_result_html.output.get("output_file_sandbox_path","")

    logger.info("--- Test: create_report (output PDF) ---")
    data_sources_json = json.dumps(["http://example.com/api/data1", "http://example.com/api/data2"])
    report_result_pdf = await tool.create_report(
        data_source_urls_json_string=data_sources_json,
        report_title="Quarterly Summary",
        output_file_sandbox_path=f"{tool.documents_dir}/quarterly_summary.pdf",
        output_format="pdf"
    )
    logger.info(f"Create Report (PDF) Result: {report_result_pdf.output or report_result_pdf.error_message}")
    assert report_result_pdf.output is not None and "quarterly_summary.pdf" in report_result_pdf.output.get("output_file_sandbox_path","")

    logger.info("--- All tests simulated. Review logs for mock command executions. ---")

if __name__ == "__main__":
    # Setup basic logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    asyncio.run(main_test())
