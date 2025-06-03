from daytona_sdk import Daytona, DaytonaConfig, CreateSandboxParams, Sandbox, SessionExecuteRequest
from daytona_api_client.models.workspace_state import WorkspaceState
from dotenv import load_dotenv
from utils.logger import logger
from utils.config import config, Configuration, EnvMode # Re-add EnvMode
from . import local_docker_handler
import os
from typing import Optional, Dict, List, Any # Added for wrapper classes

class DaytonaNotConfiguredError(Exception):
    pass

# Wrapper Classes for Local Docker Sandboxes
class LocalDockerSandboxWrapper:
    def __init__(self, container_info: Dict[str, Any], vnc_password: str):
        self.container_info = container_info
        self.id = container_info.get('container_id') # Critical: provides sandbox.id
        self.name = container_info.get('container_name')
        self._vnc_password = vnc_password # Store for potential future use

        self.fs = LocalDockerFileSystemWrapper(self.id)
        self.process = LocalDockerProcessWrapper(self.id)

    def get_preview_link(self, port_in_container: int) -> Dict[str, Optional[str]]:
        url = None
        if port_in_container == 6080 and self.container_info.get('host_vnc_port'):
            url = f"http://localhost:{self.container_info['host_vnc_port']}"
        elif port_in_container == 8080 and self.container_info.get('host_web_port'):
            url = f"http://localhost:{self.container_info['host_web_port']}"
        else:
            logger.warning(f"Preview link requested for unmapped or unknown port {port_in_container} in local Docker sandbox {self.id}")
        return {"url": url, "token": None}

class LocalDockerFileSystemWrapper:
    def __init__(self, container_id: str):
        self.container_id = container_id

    async def upload_file(self, container_path: str, content: bytes):
        logger.info(f"[LocalDockerFS] upload_file called for {self.container_id}:{container_path}. Content length: {len(content)}")
        import tempfile
        host_temp_path = None # Initialize to prevent NameError in finally if NamedTemporaryFile fails
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                host_temp_path = tmp.name

            success = local_docker_handler.upload_files_to_container(self.container_id, host_temp_path, container_path)
            if not success:
                logger.error(f"Failed to upload content to {self.container_id}:{container_path}")
            return success
        finally:
            if host_temp_path and os.path.exists(host_temp_path):
                os.remove(host_temp_path)

    def list_files(self, path: str) -> List[Dict[str, Any]]:
        logger.info(f"[LocalDockerFS] list_files called for {self.container_id}:{path}")
        return local_docker_handler.list_files_in_container(self.container_id, path)

class LocalDockerProcessWrapper:
    def __init__(self, container_id: str):
        self.container_id = container_id

    def create_session(self, session_id: str):
        logger.info(f"[LocalDockerProcess] create_session '{session_id}' called for {self.container_id}. No-op for local docker direct exec.")
        pass

    def execute_session_command(self, session_id: str, request_obj: Any) -> Dict[str, Any]:
        command = getattr(request_obj, 'command', str(request_obj))
        logger.info(f"[LocalDockerProcess] execute_session_command (session: {session_id}) in {self.container_id}: {command}")
        stdout, stderr, exit_code = local_docker_handler.execute_command_in_container(self.container_id, command)
        return {
            "output": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "is_error": exit_code != 0
        }

load_dotenv()

logger.debug("Initializing Daytona sandbox configuration")
daytona_config = DaytonaConfig(
    api_key=config.DAYTONA_API_KEY,
    server_url=config.DAYTONA_SERVER_URL,
    target=config.DAYTONA_TARGET
)

if daytona_config.api_key:
    logger.debug("Daytona API key configured successfully")
else:
    logger.warning("No Daytona API key found in environment variables")

if daytona_config.server_url:
    logger.debug(f"Daytona server URL set to: {daytona_config.server_url}")
else:
    logger.warning("No Daytona server URL found in environment variables")

if daytona_config.target:
    logger.debug(f"Daytona target set to: {daytona_config.target}")
else:
    logger.warning("No Daytona target found in environment variables")

daytona = None  # Initialize to None

if config.DAYTONA_API_KEY and config.DAYTONA_SERVER_URL:
    try:
        daytona = Daytona(daytona_config)
        logger.info("Daytona client initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Daytona client even with API key and server URL: {e}")
        daytona = None # Ensure daytona is None if initialization fails
else:
    logger.warning("Daytona client NOT initialized due to missing DAYTONA_API_KEY or DAYTONA_SERVER_URL.")

async def get_or_start_sandbox(sandbox_id: str):
    """Retrieve a sandbox by ID, check its state, and start it if needed."""
    
    global daytona
    if daytona is None:
        if config.ENV_MODE == EnvMode.LOCAL:
            logger.warning(f"Daytona client not configured. Skipping get_or_start_sandbox for sandbox ID {sandbox_id} in local mode.")
            return None
        else:
            logger.error("Daytona client is not configured. Cannot get or start sandbox.")
            raise DaytonaNotConfiguredError("Daytona client is not configured. Please check API key and server URL in environment variables.")

    logger.info(f"Getting or starting sandbox with ID: {sandbox_id}")
    
    try:
        sandbox = daytona.get_current_sandbox(sandbox_id)
        
        # Check if sandbox needs to be started
        if sandbox.instance.state == WorkspaceState.ARCHIVED or sandbox.instance.state == WorkspaceState.STOPPED:
            logger.info(f"Sandbox is in {sandbox.instance.state} state. Starting...")
            try:
                daytona.start(sandbox)
                # Wait a moment for the sandbox to initialize
                # sleep(5)
                # Refresh sandbox state after starting
                sandbox = daytona.get_current_sandbox(sandbox_id)
                
                # Start supervisord in a session when restarting
                start_supervisord_session(sandbox)
            except Exception as e:
                logger.error(f"Error starting sandbox: {e}")
                raise e
        
        logger.info(f"Sandbox {sandbox_id} is ready")
        return sandbox
        
    except Exception as e:
        logger.error(f"Error retrieving or starting sandbox: {str(e)}")
        raise e

def start_supervisord_session(sandbox: Sandbox):
    """Start supervisord in a session."""

    if daytona is None: # Though sandbox object implies daytona was available, this is for robustness
        logger.error("Daytona client is not configured. Cannot start supervisord session.")
        raise DaytonaNotConfiguredError("Daytona client is not configured. Please check API key and server URL in environment variables.")

    session_id = "supervisord-session"
    try:
        logger.info(f"Creating session {session_id} for supervisord")
        sandbox.process.create_session(session_id)
        
        # Execute supervisord command
        sandbox.process.execute_session_command(session_id, SessionExecuteRequest(
            command="exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf",
            var_async=True
        ))
        logger.info(f"Supervisord started in session {session_id}")
    except Exception as e:
        logger.error(f"Error starting supervisord session: {str(e)}")
        raise e

def create_sandbox(password: str, project_id: str = None) -> Optional[Any]: # Return type Any for now
    """Create a new sandbox using either local Docker or Daytona."""
    
    sandbox_provider = config.get('SANDBOX_TYPE', 'daytona') # Default to 'daytona'

    if sandbox_provider == 'local_docker':
        logger.info(f"Using local Docker for sandbox creation (project: {project_id}).")
        # Ensure local_docker_handler's client is available
        if not local_docker_handler.client:
            logger.error("Local Docker client in local_docker_handler is not initialized. Cannot create local Docker sandbox.")
            raise Exception("Local Docker client not initialized.")

        env_vars = {
            "VNC_PASSWORD": password,
            "RESOLUTION": "1024x768x24",
            # Add other relevant env vars from Configuration or defaults as needed
            "CHROME_PERSISTENT_SESSION": "true",
            "RESOLUTION_WIDTH": "1024",
            "RESOLUTION_HEIGHT": "768",
            "ANONYMIZED_TELEMETRY": "false", # Default, consider making configurable
            "CHROME_DEBUGGING_PORT": "9222", # Default, consider making configurable
        }
        container_info = local_docker_handler.start_sandbox_container(
            image_name=Configuration.SANDBOX_IMAGE_NAME,
            env_vars=env_vars,
            project_id=project_id
            # Optionally pass vnc_port_host, web_port_host if specific host ports are needed
        )
        if container_info:
            logger.info(f"Local Docker sandbox created: {container_info['container_id']}")
            return LocalDockerSandboxWrapper(container_info, password)
        else:
            logger.error("Failed to create local Docker sandbox.")
            raise Exception("Failed to create local Docker sandbox container.")
    
    elif sandbox_provider == 'daytona':
        logger.info(f"Using Daytona for sandbox creation (project: {project_id}).")
        global daytona
        if daytona is None:
            # This covers if SANDBOX_TYPE=daytona but daytona client failed init,
            # or if SANDBOX_TYPE=local but daytona is None (original logic for local mode when daytona was only option)
            # The EnvMode.LOCAL check was part of the original daytona-only logic.
            # If SANDBOX_TYPE is explicitly 'daytona', EnvMode.LOCAL shouldn't prevent error if daytona is None.
            if config.ENV_MODE == EnvMode.LOCAL and not (config.DAYTONA_API_KEY and config.DAYTONA_SERVER_URL):
                 logger.warning("Daytona client not configured (SANDBOX_TYPE is 'daytona' but client init failed, or running in LOCAL mode without full Daytona config). Skipping sandbox creation.")
                 return None # Or raise, depending on desired strictness for local + daytona type
            else:
                logger.error("Daytona client is not configured (SANDBOX_TYPE is 'daytona'). Cannot create Daytona sandbox.")
                raise DaytonaNotConfiguredError("Daytona client is not configured. Please check API key and server URL in environment variables.")

        logger.debug("Configuring Daytona sandbox with browser-use image and environment variables")
        labels = None
        if project_id:
            labels = {'id': project_id}

        params = CreateSandboxParams(
            image=Configuration.SANDBOX_IMAGE_NAME,
            public=True,
            labels=labels,
            env_vars={
                "CHROME_PERSISTENT_SESSION": "true",
                "RESOLUTION": "1024x768x24",
                "RESOLUTION_WIDTH": "1024",
                "RESOLUTION_HEIGHT": "768",
                "VNC_PASSWORD": password,
                "ANONYMIZED_TELEMETRY": "false",
                "CHROME_PATH": "",
                "CHROME_USER_DATA": "",
                "CHROME_DEBUGGING_PORT": "9222",
                "CHROME_DEBUGGING_HOST": "localhost",
                "CHROME_CDP": ""
            },
            resources={"cpu": 2, "memory": 4, "disk": 5}
        )
        daytona_sandbox_obj = daytona.create(params)
        logger.debug(f"Daytona Sandbox created with ID: {daytona_sandbox_obj.id}")
        start_supervisord_session(daytona_sandbox_obj)
        logger.debug(f"Daytona Sandbox environment successfully initialized")
        return daytona_sandbox_obj
    
    else:
        logger.error(f"Unsupported SANDBOX_TYPE: {sandbox_provider}")
        raise ValueError(f"Unsupported SANDBOX_TYPE: {sandbox_provider}")

async def delete_sandbox(sandbox_id: str):
    """Delete a sandbox by its ID."""
    # This function will need to be updated to handle both Daytona and local Docker sandboxes
    # For now, it retains the Daytona-specific logic.
    # A SANDBOX_TYPE check or inspection of sandbox_id format might be needed.

    global daytona
    if daytona is None: # This check might need to be more nuanced based on sandbox_provider
        if config.ENV_MODE == EnvMode.LOCAL: # Assuming EnvMode is still relevant for Daytona path
            logger.warning(f"Daytona client not configured. Skipping delete_sandbox for sandbox ID {sandbox_id} in local mode.")
            return False
        else:
            logger.error("Daytona client is not configured. Cannot delete sandbox.")
            raise DaytonaNotConfiguredError("Daytona client is not configured. Please check API key and server URL in environment variables.")

    logger.info(f"Deleting Daytona sandbox with ID: {sandbox_id}")
    
    try:
        # Get the sandbox
        sandbox = daytona.get_current_sandbox(sandbox_id)
        
        # Delete the sandbox
        daytona.remove(sandbox)
        
        logger.info(f"Successfully deleted sandbox {sandbox_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting sandbox {sandbox_id}: {str(e)}")
        raise e

