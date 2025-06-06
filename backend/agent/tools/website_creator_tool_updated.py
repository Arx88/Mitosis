import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from agentpress.tool import Tool, ToolResult, openapi_schema # xml_schema removed as it will be unused
from agentpress.thread_manager import ThreadManager

# Import necessary tools that we'll use
from agent.tools.sb_files_tool import SandboxFilesTool
from agent.tools.sb_shell_tool import SandboxShellTool
from agent.tools.sb_deploy_tool import SandboxDeployTool

logger = logging.getLogger(__name__)

@openapi_schema
class SandboxWebsiteCreatorToolParameters:
    """
    Parameters for the SandboxWebsiteCreatorTool.
    """
    # Description: The name for the website project. This will be used for the directory name.
    project_name: str
    # Description: The framework to use for the website (e.g., 'static', 'react', 'vue', 'nextjs').
    framework: str = "static"
    # Description: A brief description of the website's purpose and content.
    description: str
    # Description: A list of page names to create (e.g., ['home', 'about', 'contact']).
    pages: List[str] = ["index"]
    # Description: Whether to automatically deploy the website after creation.
    deploy: bool = False

    class Config:
        extra = "forbid"

@openapi_schema
class SandboxWebsiteCreatorToolOutput:
    """
    Output for the SandboxWebsiteCreatorTool.
    """
    # Description: The path to the created website project within the sandbox environment.
    project_path: str
    # Description: A message indicating the result of the website creation process.
    message: str
    # Description: The URL of the deployed website, if deployment was requested and successful.
    deployment_url: Optional[str] = None

    class Config:
        extra = "forbid"

class SandboxWebsiteCreatorTool(Tool):
    """Tool for creating basic website structures within the sandbox environment."""

    name = "SandboxWebsiteCreatorTool"
    description = (
        "A tool for creating website project structures (static, React, etc.) "
        "within the sandbox environment, optionally deploying the result."
    )
    parameters_schema = SandboxWebsiteCreatorToolParameters
    output_schema = SandboxWebsiteCreatorToolOutput

    def __init__(
        self,
        project_id: str,
        thread_manager: ThreadManager,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.project_id = project_id
        self.thread_manager = thread_manager

        # Initialize the tools we'll use
        self.files_tool = SandboxFilesTool(project_id, thread_manager)
        self.shell_tool = SandboxShellTool(project_id, thread_manager)
        self.deploy_tool = SandboxDeployTool(project_id, thread_manager)

        # Set up workspace paths
        self.workspace_path = "/workspace"

        # Sandbox reference will be initialized when needed
        self._sandbox = None

    async def _ensure_sandbox(self) -> Any:
        """Ensure we have a valid sandbox instance."""
        if self._sandbox is None:
            from sandbox.sandbox import get_or_start_sandbox

            if self.thread_manager is None or self.thread_manager.db is None:
                logger.error("ThreadManager or DB client not available, cannot ensure sandbox.")
                raise ValueError("Database connection not available to ensure sandbox.")

            try:
                # Get database client
                client = await self.thread_manager.db.client

                # Get or start the sandbox
                self._sandbox = await get_or_start_sandbox(self.project_id, client)

                if self._sandbox is None:
                    raise ValueError(f"Failed to get or start sandbox for project {self.project_id}")

            except Exception as e:
                logger.error(f"Error ensuring sandbox for project {self.project_id}: {str(e)}")
                raise e

        return self._sandbox

    async def run(self, parameters: SandboxWebsiteCreatorToolParameters) -> List[ToolResult]:
        """
        Create a website project structure based on the provided parameters.

        Args:
            parameters: The parameters for the website creation task

        Returns:
            List of ToolResult containing the project path and status message
        """
        logger.info(f"Running {self.name} with parameters: {parameters}")

        try:
            # Ensure sandbox is initialized
            sandbox = await self._ensure_sandbox()

            # Validate project name
            if not parameters.project_name or not parameters.project_name.isalnum():
                return [ToolResult.error("Project name must be alphanumeric.")]

            project_path = f"{self.workspace_path}/{parameters.project_name}"

            # Check if project directory already exists
            if await sandbox.fs.exists(project_path):
                return [ToolResult.error(f"Project directory 	'{project_path}	' already exists.")]

            # Create the project directory
            await sandbox.fs.mkdir(project_path)
            logger.info(f"Created project directory: {project_path}")

            # Create website structure based on framework
            if parameters.framework == "static":
                await self._create_static_structure(sandbox, project_path, parameters.pages, parameters.description)
            elif parameters.framework == "react":
                await self._create_react_structure(sandbox, project_path, parameters.project_name)
            # Add more frameworks as needed (vue, nextjs, etc.)
            # elif parameters.framework == "vue":
            #     await self._create_vue_structure(sandbox, project_path, parameters.project_name)
            # elif parameters.framework == "nextjs":
            #     await self._create_nextjs_structure(sandbox, project_path, parameters.project_name)
            else:
                await sandbox.fs.rmdir(project_path) # Clean up created directory
                return [ToolResult.error(f"Unsupported framework: {parameters.framework}")]

            # Optionally deploy the website
            deployment_url = None
            if parameters.deploy:
                deploy_result = await self._deploy_website(project_path, parameters.framework)
                if deploy_result.success:
                    deployment_url = deploy_result.output.get("url")
                    message = f"Website project created at {project_path} and deployed successfully."
                else:
                    message = f"Website project created at {project_path}, but deployment failed: {deploy_result.error}"
            else:
                message = f"Website project created successfully at {project_path}."

            # Return success
            return [
                ToolResult(
                    output=SandboxWebsiteCreatorToolOutput(
                        project_path=project_path,
                        message=message,
                        deployment_url=deployment_url,
                    )
                )
            ]

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error creating website project 	'{parameters.project_name}	': {error_message}")
            # Attempt cleanup if directory was created
            try:
                if await sandbox.fs.exists(project_path):
                    await sandbox.fs.rmdir(project_path)
            except Exception as cleanup_e:
                logger.error(f"Error during cleanup: {cleanup_e}")
            return [ToolResult.error(f"Error creating website: {error_message[:200]}")]

    async def _create_static_structure(self, sandbox: Any, project_path: str, pages: List[str], description: str) -> None:
        """Create the structure for a static website."""
        # Create index.html
        index_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{project_path.split('/')[-1]}</title>
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <h1>Welcome to {project_path.split('/')[-1]}</h1>
            <p>{description}</p>
            <nav>
                <ul>
                    {''.join([f'<li><a href="{page}.html">{page.capitalize()}</a></li>' for page in pages if page != 'index'])}
                </ul>
            </nav>
        </body>
        </html>
        """
        await sandbox.fs.write_file(f"{project_path}/index.html", index_content)

        # Create other HTML pages
        for page in pages:
            if page != "index":
                page_content = f"""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{page.capitalize()}</title>
                    <link rel="stylesheet" href="style.css">
                </head>
                <body>
                    <h1>{page.capitalize()} Page</h1>
                    <p>Content for the {page} page goes here.</p>
                    <a href="index.html">Back to Home</a>
                </body>
                </html>
                """
                await sandbox.fs.write_file(f"{project_path}/{page}.html", page_content)

        # Create style.css
        css_content = f"""
        body {{
            font-family: sans-serif;
            margin: 20px;
        }}
        h1 {{
            color: #333;
        }}
        nav ul {{
            list-style: none;
            padding: 0;
        }}
        nav li {{
            display: inline;
            margin-right: 10px;
        }}
        """
        await sandbox.fs.write_file(f"{project_path}/style.css", css_content)
        logger.info(f"Created static site structure in {project_path}")

    async def _create_react_structure(self, sandbox: Any, project_path: str, project_name: str) -> None:
        """Create the structure for a React website using Vite."""
        # Use shell tool to run Vite command
        # Ensure Node.js and npm/yarn are available in the sandbox
        command = f"cd {self.workspace_path} && npm create vite@latest {project_name} -- --template react"

        logger.info(f"Running command to create React app: {command}")
        # Need to handle interactive prompts from Vite
        # This might require a more sophisticated shell interaction or a non-interactive template

        # Simplified approach: Assume non-interactive or handle prompts
        # For now, we'll just log the command. Actual execution might need refinement.
        # result = await self.shell_tool.run(command=command, working_dir=self.workspace_path)

        # Placeholder: Create basic files manually until shell interaction is robust
        await sandbox.fs.write_file(f"{project_path}/src/App.jsx", """
        import React from 'react';

        function App() {
          return (
            <div>
              <h1>Welcome to {project_name} (React App)</h1>
              <p>Edit src/App.jsx to start building!</p>
            </div>
          );
        }

        export default App;
        """)
        await sandbox.fs.write_file(f"{project_path}/index.html", """
        <!DOCTYPE html>
        <html lang="en">
          <head>
            <meta charset="UTF-8" />
            <link rel="icon" type="image/svg+xml" href="/vite.svg" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>{project_name}</title>
          </head>
          <body>
            <div id="root"></div>
            <script type="module" src="/src/main.jsx"></script>
          </body>
        </html>
        """)
        await sandbox.fs.write_file(f"{project_path}/src/main.jsx", """
        import React from 'react'
        import ReactDOM from 'react-dom/client'
        import App from './App.jsx'

        ReactDOM.createRoot(document.getElementById('root')).render(
          <React.StrictMode>
            <App />
          </React.StrictMode>,
        )
        """)
        await sandbox.fs.write_file(f"{project_path}/package.json", json.dumps({
            "name": project_name,
            "private": True,
            "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "lint": "eslint . --ext js,jsx --report-unused-disable-directives --max-warnings 0",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0"
            },
            "devDependencies": {
                "@types/react": "^18.2.66",
                "@types/react-dom": "^18.2.22",
                "@vitejs/plugin-react": "^4.2.1",
                "eslint": "^8.57.0",
                "eslint-plugin-react": "^7.34.1",
                "eslint-plugin-react-hooks": "^4.6.0",
                "eslint-plugin-react-refresh": "^0.4.6",
                "vite": "^5.2.0"
            }
        }, indent=2))

        logger.info(f"Created basic React app structure in {project_path}. Manual build steps might be needed.")
        # Note: This manual creation is a placeholder. Using `npm create vite` via shell is preferred.

    async def _deploy_website(self, project_path: str, framework: str) -> ToolResult:
        """Deploy the website using the SandboxDeployTool."""
        logger.info(f"Attempting to deploy website from {project_path}")

        # Determine the build directory based on the framework
        build_dir = project_path # Default for static
        if framework == "react":
            # Need to run build command first
            build_command = f"cd {project_path} && npm install && npm run build"
            logger.info(f"Running build command: {build_command}")
            # build_result = await self.shell_tool.run(command=build_command, working_dir=project_path)
            # if build_result.error:
            #     return ToolResult.error(f"Build failed: {build_result.error}")
            build_dir = f"{project_path}/dist" # Default Vite build output
            logger.warning("Skipping build step due to shell limitations. Assuming build dir exists at /dist")

        # Use the deploy tool
        # Assuming deploy tool handles framework type or expects a static build directory
        deploy_params = {
            "project_dir": build_dir,
            "framework": "static" # Deploy tool might expect static assets
        }

        try:
            # Call the deploy tool's run method directly
            deploy_results = await self.deploy_tool.run(self.deploy_tool.parameters_schema(**deploy_params))

            if deploy_results and deploy_results[0].success:
                logger.info(f"Deployment successful: {deploy_results[0].output}")
                return deploy_results[0]
            else:
                error_msg = deploy_results[0].error if deploy_results else "Unknown deployment error"
                logger.error(f"Deployment failed: {error_msg}")
                return ToolResult.error(f"Deployment failed: {error_msg}")

        except Exception as e:
            logger.error(f"Error during deployment: {str(e)}")
            return ToolResult.error(f"Error during deployment: {str(e)}")
```
