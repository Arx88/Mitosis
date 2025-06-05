import os
import json
import logging
import tempfile
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from agent_protocol import Tool, ToolResult
from agent_protocol.models import (
    openapi_schema,
    xml_schema,
)

from ..utils.sandbox import SandboxToolsBase
from ..utils.threads import ThreadManager


logger = logging.getLogger(__name__)


@openapi_schema
class SandboxDocumentGenerationToolParameters(SandboxToolsBase.SandboxFileOperationMixin):
    """
    Parameters for the SandboxDocumentGenerationTool.
    """

    content: str = xml_schema(
        description="The HTML content to be converted to PDF or other document formats.",
        tag_name="content",
    )
    output_format: str = xml_schema(
        description="The desired output format (e.g., 'pdf', 'png'). Defaults to 'pdf'.",
        tag_name="output_format",
        default="pdf",
    )
    output_filename: Optional[str] = xml_schema(
        description="The desired filename for the output document. If not provided, a default name will be generated.",
        tag_name="output_filename",
        default=None,
    )

    class Config:
        extra = "forbid"


@openapi_schema
class SandboxDocumentGenerationToolOutput(SandboxToolsBase.SandboxFileOperationMixin):
    """
    Output for the SandboxDocumentGenerationTool.
    """

    document_path: str = xml_schema(
        description="The path to the generated document within the sandbox environment.",
        tag_name="document_path",
    )
    message: str = xml_schema(
        description="A message indicating the result of the document generation.",
        tag_name="message",
    )

    class Config:
        extra = "forbid"


class SandboxDocumentGenerationTool(Tool[SandboxDocumentGenerationToolParameters, SandboxDocumentGenerationToolOutput]):
    """
    A tool for generating documents (e.g., PDFs) from HTML content within a sandbox environment.
    """

    name = "SandboxDocumentGenerationTool"
    description = (
        "Generates documents (e.g., PDFs, PNGs) from HTML content using WeasyPrint "
        "within the sandbox environment. Saves the generated document to the sandbox."
    )
    parameters_schema = SandboxDocumentGenerationToolParameters
    output_schema = SandboxDocumentGenerationToolOutput

    def __init__(
        self,
        sandbox: SandboxToolsBase,
        thread_manager: ThreadManager,
        workspace: str,
        hostname: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.sandbox = sandbox
        self.thread_manager = thread_manager
        self.workspace = workspace
        self.hostname = hostname

    async def run(self, parameters: SandboxDocumentGenerationToolParameters) -> List[ToolResult]:
        logger.info(f"Running {self.name} with parameters: {parameters}")

        if not self.sandbox.is_running:
            return [
                ToolResult.error("Sandbox is not running. Please start the sandbox first.")
            ]

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if parameters.output_filename:
                if not parameters.output_filename.endswith(f".{parameters.output_format}"):
                    output_filename = f"{parameters.output_filename}_{timestamp}.{parameters.output_format}"
                else:
                    # Ensure filename is unique if it's fully provided
                    base, ext = os.path.splitext(parameters.output_filename)
                    output_filename = f"{base}_{timestamp}{ext}"
            else:
                output_filename = f"generated_document_{timestamp}.{parameters.output_format}"

            # Create a temporary HTML file in the host system
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".html", encoding="utf-8"
            ) as tmp_html_file:
                tmp_html_file.write(parameters.content)
                host_html_path = tmp_html_file.name

            sandbox_html_path = os.path.join(self.sandbox.sandbox_workspace, os.path.basename(host_html_path))
            sandbox_output_path = os.path.join(self.sandbox.sandbox_workspace, output_filename)

            # Upload the HTML file to the sandbox
            await self.sandbox.upload_file(host_html_path, sandbox_html_path)

            # Command to generate the document in the sandbox
            # Ensure WeasyPrint is installed: python -m pip install weasyprint
            # For PNG output, additional dependencies might be needed (e.g., cairocffi, pangocffi)
            # sudo apt-get update && sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2
            cmd = [
                "python",
                "-m",
                "weasyprint",
                sandbox_html_path,
                sandbox_output_path,
            ]
            if parameters.output_format != "pdf":
                cmd.extend(["-f", parameters.output_format])


            logger.info(f"Executing command in sandbox: {' '.join(cmd)}")
            process_output = await self.sandbox.run_command(" ".join(cmd), timeout=120) # Increased timeout for potentially long conversions

            if process_output.exit_code != 0:
                logger.error(f"Error generating document: {process_output.stderr}")
                # Attempt to download any partial output or logs if generation fails
                # This might not always be possible or yield useful results.
                try:
                    local_error_output_path = os.path.join(self.workspace, f"error_{output_filename}")
                    await self.sandbox.download_file(sandbox_output_path, local_error_output_path)
                    error_message = (
                        f"Document generation failed. Exit code: {process_output.exit_code}. "
                        f"Stderr: {process_output.stderr}. "
                        f"Attempted to download output to: {local_error_output_path}"
                    )
                except Exception as e:
                    logger.error(f"Could not download error output: {e}")
                    error_message = (
                        f"Document generation failed. Exit code: {process_output.exit_code}. "
                        f"Stderr: {process_output.stderr}. "
                        f"Additionally, failed to download any partial output from sandbox."
                    )
                return [ToolResult.error(error_message)]

            # Verify the output file exists in the sandbox
            if not await self.sandbox.file_exists(sandbox_output_path):
                 # Attempt to list directory contents for debugging
                dir_listing = await self.sandbox.run_command(f"ls -la {self.sandbox.sandbox_workspace}")
                logger.error(f"Output file {sandbox_output_path} not found in sandbox after generation. Dir listing: {dir_listing.stdout} {dir_listing.stderr}")
                return [ToolResult.error(f"Output file {sandbox_output_path} not found in sandbox after successful command execution. This might indicate an issue with WeasyPrint or the sandbox environment. Stderr: {process_output.stderr}, Stdout: {process_output.stdout}")]


            # Download the generated document from the sandbox to the host workspace
            local_output_path = os.path.join(self.workspace, output_filename)
            await self.sandbox.download_file(sandbox_output_path, local_output_path)
            logger.info(f"Document downloaded to: {local_output_path}")

            # Clean up the temporary HTML file from the host and sandbox
            os.remove(host_html_path)
            await self.sandbox.run_command(f"rm {sandbox_html_path}")
            # Optionally, remove the generated file from sandbox if only local copy is needed
            # await self.sandbox.run_command(f"rm {sandbox_output_path}")


            return [
                ToolResult(
                    output=SandboxDocumentGenerationToolOutput(
                        document_path=local_output_path, # Return path on the host system
                        message=f"Document '{output_filename}' generated successfully and saved to '{local_output_path}'.",
                    )
                )
            ]

        except Exception as e:
            logger.exception(f"An unexpected error occurred in {self.name}: {e}")
            return [
                ToolResult.error(f"An unexpected error occurred: {str(e)}")
            ]

    async def _ensure_dependencies_installed(self) -> bool:
        """
        Ensures that WeasyPrint and its dependencies are installed in the sandbox.
        Returns True if successful or already installed, False otherwise.
        """
        if not self.sandbox.is_running:
            logger.error("Sandbox is not running, cannot check/install dependencies.")
            return False

        # Check if weasyprint is installed
        check_cmd = "python -m weasyprint --version"
        process_output = await self.sandbox.run_command(check_cmd, timeout=30)

        if process_output.exit_code == 0:
            logger.info(f"WeasyPrint already installed: {process_output.stdout.strip()}")
            return True
        else:
            logger.info("WeasyPrint not found or check failed, attempting installation.")
            # Install WeasyPrint and its Pango/Cairo dependencies for formats like PNG
            install_cmds = [
                "sudo apt-get update -y",
                "sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 libffi-dev", # Added libffi-dev
                "python -m pip install --upgrade pip",
                "python -m pip install weasyprint cairocffi" # cairocffi for PNGs
            ]
            for cmd in install_cmds:
                logger.info(f"Running installation command: {cmd}")
                install_proc = await self.sandbox.run_command(cmd, timeout=300) # Long timeout for apt-get
                if install_proc.exit_code != 0:
                    logger.error(f"Failed to execute '{cmd}': {install_proc.stderr}")
                    # If apt-get update fails, it might be a network issue or sources list problem.
                    if "apt-get update" in cmd and "Failed to fetch" in install_proc.stderr:
                         logger.error("apt-get update failed. This might be due to network issues or outdated package lists in the sandbox environment.")
                    return False
            logger.info("WeasyPrint and dependencies installation attempt finished.")
            # Verify installation
            verify_proc = await self.sandbox.run_command(check_cmd, timeout=30)
            if verify_proc.exit_code == 0:
                logger.info(f"WeasyPrint successfully installed: {verify_proc.stdout.strip()}")
                return True
            else:
                logger.error(f"Failed to install WeasyPrint. Verification command stderr: {verify_proc.stderr}")
                return False

    async def on_sandbox_start(self):
        """
        Hook called when the sandbox is started.
        Ensures WeasyPrint and its dependencies are installed.
        """
        logger.info("Sandbox started, ensuring WeasyPrint dependencies are installed.")
        installed = await self._ensure_dependencies_installed()
        if not installed:
            logger.error(
                "Failed to install WeasyPrint dependencies in the sandbox. "
                "Document generation may fail."
            )
        else:
            logger.info("WeasyPrint dependencies are present in the sandbox.")

    @classmethod
    def primjer(cls) -> "SandboxDocumentGenerationTool":
        # This is a placeholder for example instantiation.
        # Actual instantiation will depend on the application's DI framework.
        class MockSandbox(SandboxToolsBase):
            is_running = True
            sandbox_workspace = "/mnt/sandbox_workspace"
            async def run_command(self, command: str, timeout: int = 60) -> Any:
                print(f"MockSandbox: Running command: {command}")
                class MockProc:
                    exit_code = 0
                    stdout = ""
                    stderr = ""
                if "weasyprint --version" in command and "initial_check" not in command : #Simulate not installed initially for test
                    if not hasattr(self, 'installed_weasyprint'):
                        self.installed_weasyprint = False # Simulate not installed first time
                        return MockProc()
                if "python -m pip install weasyprint" in command:
                    self.installed_weasyprint = True
                    return MockProc()

                if "weasyprint --version" in command and hasattr(self, 'installed_weasyprint') and self.installed_weasyprint:
                    mp = MockProc()
                    mp.stdout = "WeasyPrint 52.5 (mocked)"
                    return mp


                return MockProc()
            async def upload_file(self, host_path: str, sandbox_path: str) -> None:
                print(f"MockSandbox: Uploading {host_path} to {sandbox_path}")
            async def download_file(self, sandbox_path: str, host_path: str) -> None:
                print(f"MockSandbox: Downloading {sandbox_path} to {host_path}")
                # Create a dummy file for testing download
                with open(host_path, "w") as f:
                    f.write("dummy pdf content")
            async def file_exists(self, sandbox_path: str) -> bool:
                print(f"MockSandbox: Checking if {sandbox_path} exists")
                return True # Assume file always exists after generation for mock

        class MockThreadManager(ThreadManager):
            def __init__(self):
                super().__init__(max_threads=1) # Or appropriate number
            async def run_in_thread(self, func, *args, **kwargs):
                return await func(*args, **kwargs)


        mock_sandbox = MockSandbox()
        mock_thread_manager = MockThreadManager()
        # Example usage:
        # tool = cls(
        #     sandbox=mock_sandbox,
        #     thread_manager=mock_thread_manager,
        #     workspace="/tmp/workspace",
        #     hostname="http://localhost:8000",
        # )
        # asyncio.run(tool.on_sandbox_start()) # Ensure dependencies
        # result = asyncio.run(tool.run(SandboxDocumentGenerationToolParameters(content="<h1>Hello</h1>", output_filename="test.pdf")))
        # print(result)
        raise NotImplementedError("This method is for demonstration and should not be called directly.")

# Example of how to run the on_sandbox_start manually for testing if needed
async def main_test():
    class MockSandbox(SandboxToolsBase):
        is_running = True
        sandbox_workspace = "/mnt/sandbox_workspace"
        _weasyprint_installed = False

        async def run_command(self, command: str, timeout: int = 60) -> Any:
            logger.info(f"MockSandbox: Running command: '{command}'")
            class MockProc:
                def __init__(self, exit_code=0, stdout="", stderr=""):
                    self.exit_code = exit_code
                    self.stdout = stdout
                    self.stderr = stderr

            if "weasyprint --version" in command:
                if self._weasyprint_installed:
                    return MockProc(stdout="WeasyPrint 52.5 (mocked)")
                else:
                    return MockProc(exit_code=1, stderr="not found") # Simulate not installed
            elif "apt-get update" in command:
                logger.info("MockSandbox: Simulating apt-get update.")
                await asyncio.sleep(1) # Simulate time taken
                return MockProc()
            elif "apt-get install" in command:
                logger.info(f"MockSandbox: Simulating apt-get install for command: {command}")
                await asyncio.sleep(1)
                return MockProc()
            elif "python -m pip install" in command:
                logger.info(f"MockSandbox: Simulating pip install for command: {command}")
                await asyncio.sleep(1)
                self._weasyprint_installed = "weasyprint" in command # Mark as installed
                return MockProc()
            elif "rm" in command:
                logger.info(f"MockSandbox: Simulating rm command: {command}")
                return MockProc()
            elif "ls -la" in command:
                logger.info(f"MockSandbox: Simulating ls -la command: {command}")
                return MockProc(stdout="drwxr-xr-x 2 root root 4096 Jul 22 10:00 .")
            else:
                logger.warning(f"MockSandbox: Unhandled command: {command}")
                return MockProc(exit_code=127, stderr="command not found")

        async def upload_file(self, host_path: str, sandbox_path: str) -> None:
            logger.info(f"MockSandbox: Uploading {host_path} to {sandbox_path}")
            # Simulate file being available in sandbox
            self._sandbox_files = getattr(self, '_sandbox_files', {})
            self._sandbox_files[sandbox_path] = True


        async def download_file(self, sandbox_path: str, host_path: str) -> None:
            logger.info(f"MockSandbox: Downloading {sandbox_path} to {host_path}")
            if not await self.file_exists(sandbox_path):
                raise FileNotFoundError(f"MockSandbox: File {sandbox_path} not found for download.")
            # Create a dummy file for testing download
            os.makedirs(os.path.dirname(host_path), exist_ok=True)
            with open(host_path, "w") as f:
                f.write("dummy pdf content from mock download")
            logger.info(f"MockSandbox: Created dummy downloaded file at {host_path}")


        async def file_exists(self, sandbox_path: str) -> bool:
            exists = getattr(self, '_sandbox_files', {}).get(sandbox_path, False)
            logger.info(f"MockSandbox: Checking if {sandbox_path} exists: {exists}")
            # Simulate file existing after weasyprint command for the output file
            if "generated_document" in sandbox_path and not exists: # Crude check
                 # Assume weasyprint command "created" it
                logger.info(f"MockSandbox: Simulating {sandbox_path} now exists after generation.")
                return True
            return exists


    class MockThreadManager(ThreadManager):
        def __init__(self):
            super().__init__(max_threads=3)
        async def run_in_thread(self, func, *args, **kwargs):
            # In test, run directly or use actual threads if testing concurrency
            return await func(*args, **kwargs)

    logging.basicConfig(level=logging.INFO)
    logger.info("Starting main_test for SandboxDocumentGenerationTool")

    mock_sandbox = MockSandbox()
    mock_thread_manager = MockThreadManager()
    tool = SandboxDocumentGenerationTool(
        sandbox=mock_sandbox,
        thread_manager=mock_thread_manager,
        workspace=tempfile.gettempdir(), # Use actual temp dir for workspace in test
        hostname="http://localhost:8000", # Or relevant hostname
    )

    logger.info("Running on_sandbox_start...")
    await tool.on_sandbox_start()
    logger.info("on_sandbox_start finished.")

    logger.info("Testing PDF generation...")
    params_pdf = SandboxDocumentGenerationToolParameters(
        content="<h1>Hello PDF</h1><p>This is a test PDF.</p>",
        output_format="pdf",
        output_filename="test_output" #.pdf will be added
    )
    results_pdf = await tool.run(params_pdf)
    for result in results_pdf:
        if result.is_error:
            logger.error(f"PDF Generation Error: {result.error_message}")
        else:
            logger.info(f"PDF Generation Success: {result.output}")
            assert isinstance(result.output, SandboxDocumentGenerationToolOutput)
            assert "test_output" in result.output.document_path
            assert result.output.document_path.endswith(".pdf")
            assert os.path.exists(result.output.document_path), f"Output file {result.output.document_path} does not exist"
            os.remove(result.output.document_path) # Clean up

    logger.info("Testing PNG generation...")
    params_png = SandboxDocumentGenerationToolParameters(
        content="<h1>Hello PNG</h1><p>This is a test PNG.</p><style>body { background-color: lightblue; }</style>",
        output_format="png",
        # output_filename="test_output.png" # Test with full extension
    )
    results_png = await tool.run(params_png)
    for result in results_png:
        if result.is_error:
            logger.error(f"PNG Generation Error: {result.error_message}")
        else:
            logger.info(f"PNG Generation Success: {result.output}")
            assert isinstance(result.output, SandboxDocumentGenerationToolOutput)
            assert "generated_document" in result.output.document_path # Default name
            assert result.output.document_path.endswith(".png")
            assert os.path.exists(result.output.document_path), f"Output file {result.output.document_path} does not exist"
            os.remove(result.output.document_path) # Clean up

    logger.info("main_test finished.")


if __name__ == "__main__":
    # This allows running the test logic if the file is executed directly.
    # Note: This is for local testing and might need adjustments
    # depending on the project structure and how Sandbox/ThreadManager are initialized.
    # To run: python backend/agent/tools/document_generation_tool.py
    asyncio.run(main_test())
