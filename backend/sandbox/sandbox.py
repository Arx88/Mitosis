from daytona_sdk import Daytona, DaytonaConfig, CreateSandboxParams, Sandbox, SessionExecuteRequest
from daytona_api_client.models.workspace_state import WorkspaceState
from dotenv import load_dotenv
from utils.logger import logger
from utils.config import config, Configuration, EnvMode
from . import local_docker_handler
import os
from services.supabase import DBConnection # Added DBConnection import
from typing import Optional, Dict, List, Any # Added for wrapper classes

class DaytonaNotConfiguredError(Exception):
    pass

class LocalDockerUnavailableError(Exception):
    """Custom exception for when the local Docker client cannot be initialized or is unusable."""
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

    async def create_folder(self, folder_path: str, permissions: str = "755") -> bool:
        logger.info(f"[LocalDockerFS] create_folder called for {self.container_id}:{folder_path} with permissions {permissions}")

        # Create the folder
        mkdir_command = f"mkdir -p {folder_path}"
        logger.debug(f"[LocalDockerFS] Executing mkdir command: {mkdir_command} in {self.container_id}")
        stdout_mkdir, stderr_mkdir, exit_code_mkdir = local_docker_handler.execute_command_in_container(
            container_id=self.container_id,
            command=mkdir_command
        )

        if exit_code_mkdir != 0:
            logger.error(f"[LocalDockerFS] Failed to create folder {folder_path} in {self.container_id}. Exit code: {exit_code_mkdir}, Stderr: {stderr_mkdir}")
            return False
        logger.info(f"[LocalDockerFS] Successfully created folder {folder_path} in {self.container_id}")

        # Set permissions
        chmod_command = f"chmod {permissions} {folder_path}"
        logger.debug(f"[LocalDockerFS] Executing chmod command: {chmod_command} in {self.container_id}")
        stdout_chmod, stderr_chmod, exit_code_chmod = local_docker_handler.execute_command_in_container(
            container_id=self.container_id,
            command=chmod_command
        )

        if exit_code_chmod != 0:
            logger.error(f"[LocalDockerFS] Failed to set permissions {permissions} for folder {folder_path} in {self.container_id}. Exit code: {exit_code_chmod}, Stderr: {stderr_chmod}")
            # Optionally, consider if you should try to clean up the created folder if chmod fails.
            # For now, returning False indicates the operation wasn't fully successful.
            return False
        logger.info(f"[LocalDockerFS] Successfully set permissions {permissions} for folder {folder_path} in {self.container_id}")

        return True

    async def set_file_permissions(self, file_path: str, permissions: str) -> bool:
        logger.info(f"[LocalDockerFS] set_file_permissions called for {self.container_id}:{file_path} with permissions {permissions}")

        chmod_command = f"chmod {permissions} {file_path}"
        logger.debug(f"[LocalDockerFS] Executing chmod command for file: {chmod_command} in {self.container_id}")

        stdout_chmod, stderr_chmod, exit_code_chmod = local_docker_handler.execute_command_in_container(
            container_id=self.container_id,
            command=chmod_command
        )

        if exit_code_chmod != 0:
            logger.error(f"[LocalDockerFS] Failed to set permissions {permissions} for file {file_path} in {self.container_id}. Exit code: {exit_code_chmod}, Stderr: {stderr_chmod}")
            return False

        logger.info(f"[LocalDockerFS] Successfully set permissions {permissions} for file {file_path} in {self.container_id}")
        return True

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

async def get_or_start_sandbox(project_id: str, db_client) -> Optional[Any]:
    """Retrieve a sandbox by project_id, check its state, and prepare it if needed."""
    logger.info(f"Getting or starting sandbox for project_id: {project_id}")

    try:
        project_result = await db_client.table('projects').select('sandbox').eq('project_id', project_id).maybe_single().execute()
        if not project_result.data or not project_result.data.get('sandbox'):
            logger.error(f"No project data or sandbox info found for project_id: {project_id}")
            raise Exception(f"Sandbox information missing for project {project_id}")

        sandbox_info = project_result.data['sandbox']
        sandbox_type = sandbox_info.get('type')
        actual_sandbox_id = sandbox_info.get('id')

        if not actual_sandbox_id or not sandbox_type:
            logger.error(f"Sandbox ID or type missing in DB for project_id: {project_id}. Sandbox info: {sandbox_info}")
            raise Exception(f"Sandbox ID or type malformed for project {project_id}")

        if sandbox_type == 'local_docker':
            logger.info(f"Handling as local_docker sandbox: {actual_sandbox_id}")
            # Preemptive client check removed, local_docker_handler will attempt init.

            status = local_docker_handler.get_sandbox_container_status(actual_sandbox_id)

            if status is None: # Indicates client was not available in local_docker_handler
                logger.error(f"Failed to get status for local_docker sandbox {actual_sandbox_id} because Docker client is unavailable.")
                raise LocalDockerUnavailableError("Local Docker client not available or failed to initialize.")

            logger.info(f"Local Docker container {actual_sandbox_id} status: {status}")

            if status == 'running':
                container_details_for_wrapper = {
                    'container_id': actual_sandbox_id,
                    'container_name': sandbox_info.get('name'),
                    'host_vnc_port': sandbox_info.get('vnc_preview', '').split(':')[-1] if sandbox_info.get('vnc_preview') else None,
                    'host_web_port': sandbox_info.get('sandbox_url', '').split(':')[-1] if sandbox_info.get('sandbox_url') else None,
                }
                if container_details_for_wrapper['host_vnc_port']:
                    try: container_details_for_wrapper['host_vnc_port'] = int(container_details_for_wrapper['host_vnc_port'])
                    except ValueError: container_details_for_wrapper['host_vnc_port'] = None
                if container_details_for_wrapper['host_web_port']:
                    try: container_details_for_wrapper['host_web_port'] = int(container_details_for_wrapper['host_web_port'])
                    except ValueError: container_details_for_wrapper['host_web_port'] = None

                return LocalDockerSandboxWrapper(container_details_for_wrapper, sandbox_info.get('pass'))
            elif status in ['created', 'exited', 'stopped']:
                logger.info(f"Local Docker container {actual_sandbox_id} is not running ({status}). Attempting to start.")
                try:
                    # Attempt to get client again, or rely on it being available if status check passed.
                    # For starting, local_docker_handler doesn't have a direct "start_container" that also inits client.
                    # This part of the logic might need a small helper in local_docker_handler or careful handling here.
                    # For now, let's assume if get_sandbox_container_status worked, client is somewhat available.
                    # However, the original code used local_docker_handler.client directly.
                    # This implies a direct client access that might be an issue with the new model.
                    # A better approach would be local_docker_handler.start_container(id) if it existed and handled client init.
                    # Given the current tools, we'll proceed, but this is a potential refinement area.
                    # The _get_or_initialize_client is global in local_docker_handler, so subsequent calls in this block
                    # to local_docker_handler.client (if it were still used) would benefit from the first call's init.
                    # However, we should use a local_docker_handler function if possible.
                    # Re-evaluating: local_docker_handler.client is no longer directly accessible in the intended way.
                    # This block needs to call a function in local_docker_handler that can start the container.
                    # There isn't one. This reveals a gap.
                    # For the scope of *this specific subtask*, we are only removing preemptive checks.
                    # The original code `docker_sdk_client = local_docker_handler.client` will fail if client is None.
                    # The `_get_or_initialize_client()` is not directly called here.
                    # This means the start logic might fail if the client wasn't initialized by `get_sandbox_container_status`.
                    # Let's assume `local_docker_handler.start_sandbox_container` is for *new* containers.
                    # For existing ones, Docker SDK is used directly.
                    # This part of the code in `get_or_start_sandbox` might implicitly rely on `client` being populated
                    # by the `get_sandbox_container_status` call.

                    # Let's assume for now the existing logic for starting an existing container is slightly outside
                    # the direct "on-demand init" for *new operations*, and might need a follow-up.
                    # The most direct interpretation of the task is to remove the *initial* check.
                    # The line `docker_sdk_client = local_docker_handler.client` is problematic.
                    # It should be: `docker_sdk_client = local_docker_handler._get_or_initialize_client()`
                    # Or better, local_docker_handler should expose a start_existing_container(id) function.
                    # Let's make the minimal change to use _get_or_initialize_client() here for now.
                    docker_sdk_client = local_docker_handler._get_or_initialize_client()
                    if not docker_sdk_client:
                        raise LocalDockerUnavailableError("Local Docker client not available to start existing container.")

                    container_obj = docker_sdk_client.containers.get(actual_sandbox_id)
                    container_obj.start()
                    logger.info(f"Successfully started local Docker container {actual_sandbox_id}.")
                    container_obj.reload()
                    host_vnc_port_restarted = container_obj.ports.get('6080/tcp')[0]['HostPort'] if container_obj.ports.get('6080/tcp') else None
                    host_web_port_restarted = container_obj.ports.get('8080/tcp')[0]['HostPort'] if container_obj.ports.get('8080/tcp') else None

                    container_details_restarted = {
                        'container_id': actual_sandbox_id,
                        'container_name': sandbox_info.get('name'),
                        'host_vnc_port': host_vnc_port_restarted,
                        'host_web_port': host_web_port_restarted,
                    }
                    return LocalDockerSandboxWrapper(container_details_restarted, sandbox_info.get('pass'))
                except Exception as e_start:
                    logger.error(f"Failed to start local Docker container {actual_sandbox_id}: {e_start}")
                    return None
            else:
                logger.warning(f"Local Docker container {actual_sandbox_id} in unusable state: {status}. Cannot provide sandbox.")
                return None

        elif sandbox_type == 'daytona':
            logger.info(f"Handling as Daytona sandbox: {actual_sandbox_id}")
            global daytona
            if daytona is None:
                raise DaytonaNotConfiguredError("Daytona client not configured (SANDBOX_TYPE is 'daytona').")

            daytona_sandbox = daytona.get_current_sandbox(actual_sandbox_id)
            if daytona_sandbox.instance.state == WorkspaceState.ARCHIVED or daytona_sandbox.instance.state == WorkspaceState.STOPPED:
                logger.info(f"Daytona sandbox {actual_sandbox_id} is {daytona_sandbox.instance.state}. Starting...")
                daytona.start(daytona_sandbox)
                daytona_sandbox = daytona.get_current_sandbox(actual_sandbox_id)
                start_supervisord_session(daytona_sandbox)
            logger.info(f"Daytona sandbox {actual_sandbox_id} is ready.")
            return daytona_sandbox
        
        else:
            logger.error(f"Unsupported sandbox_type '{sandbox_type}' for project {project_id}")
            raise ValueError(f"Unsupported sandbox_type '{sandbox_type}'")

    except Exception as e:
        logger.error(f"Error in get_or_start_sandbox for project {project_id}: {e}", exc_info=True)
        return None

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

        # Preemptive client check removed, local_docker_handler.start_sandbox_container will attempt init.

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
            logger.error(f"Failed to create local Docker sandbox for project {project_id} (start_sandbox_container returned None).")
            raise LocalDockerUnavailableError(
                f"Failed to start local Docker sandbox container for project {project_id}. Check previous logs from local_docker_handler."
            )
    
    elif sandbox_provider == 'daytona':
        logger.info(f"Using Daytona for sandbox creation (project: {project_id}).")
        global daytona
        if daytona is None:
            # This covers if SANDBOX_TYPE=daytona but daytona client failed init,
            # or if SANDBOX_TYPE=local but daytona is None (original logic for local mode when daytona was only option)
            # The EnvMode.LOCAL check was part of the original daytona-only logic.
            # If SANDBOX_TYPE is explicitly 'daytona', EnvMode.LOCAL shouldn't prevent error if daytona is None.
            if config.ENV_MODE == EnvMode.LOCAL and not (config.DAYTONA_API_KEY and config.DAYTONA_SERVER_URL): # Check if EnvMode is available
                 logger.warning("Daytona client not configured (SANDBOX_TYPE is 'daytona' but client init failed, or running in LOCAL mode without full Daytona config). Skipping sandbox creation.")
                 return None
            else:
                logger.error("Daytona client is not configured (SANDBOX_TYPE is 'daytona'). Cannot create sandbox.")
                raise DaytonaNotConfiguredError("Daytona client is not configured. Please check API key and server URL in environment variables.")

        logger.debug("Configuring Daytona sandbox with browser-use image and environment variables")
        # Ensure CreateSandboxParams is imported if not already
        # from daytona_sdk import CreateSandboxParams # This was already at the top
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

async def delete_sandbox(project_id: str, db_client) -> bool:
    """Delete a sandbox by project_id, handling either local Docker or Daytona."""
    logger.info(f"Deleting sandbox for project_id: {project_id}")

    try:
        project_result = await db_client.table('projects').select('sandbox').eq('project_id', project_id).maybe_single().execute()
        if not project_result.data or not project_result.data.get('sandbox'):
            logger.warning(f"No project data or sandbox info found for project_id: {project_id}. Nothing to delete.")
            return True

        sandbox_info = project_result.data['sandbox']
        sandbox_type = sandbox_info.get('type')
        actual_sandbox_id = sandbox_info.get('id')

        if not actual_sandbox_id or not sandbox_type:
            logger.warning(f"Sandbox ID or type missing for project_id: {project_id}. Cannot delete. Info: {sandbox_info}")
            await db_client.table('projects').update({'sandbox': None}).eq('project_id', project_id).execute()
            return False

        deleted_successfully = False
        if sandbox_type == 'local_docker':
            logger.info(f"Deleting local_docker sandbox: {actual_sandbox_id}")
            # Preemptive client check removed, local_docker_handler.stop_and_remove_sandbox_container will attempt init.
            # The function stop_and_remove_sandbox_container returns False if client is not available.
            deleted_successfully = local_docker_handler.stop_and_remove_sandbox_container(actual_sandbox_id, raise_not_found=False)
            if not deleted_successfully and local_docker_handler._get_or_initialize_client() is None: # Check if failure was due to client
                 logger.error("Failed to delete local_docker sandbox because Docker client is unavailable.")
                 # deleted_successfully is already False, this log gives more context.
                 # Consider if a specific error should be raised or if current handling is enough.
                 # For now, matching existing behavior: it would have been false, and DB record not cleared.

        elif sandbox_type == 'daytona':
            logger.info(f"Deleting Daytona sandbox: {actual_sandbox_id}")
            global daytona
            if daytona is None:
                logger.error("Daytona client not configured. Cannot delete Daytona sandbox.")
                deleted_successfully = False
            else:
                try:
                    daytona_sandbox_obj = daytona.get_current_sandbox(actual_sandbox_id)
                    daytona.remove(daytona_sandbox_obj)
                    logger.info(f"Successfully deleted Daytona sandbox {actual_sandbox_id}")
                    deleted_successfully = True
                except Exception as e_daytona_del:
                    logger.error(f"Error deleting Daytona sandbox {actual_sandbox_id}: {e_daytona_del}")
                    if "not found" in str(e_daytona_del).lower():
                        logger.warning(f"Daytona sandbox {actual_sandbox_id} was already not found or gone.")
                        deleted_successfully = True
                    else:
                        deleted_successfully = False
        
        else:
            logger.error(f"Unsupported sandbox_type '{sandbox_type}' for project {project_id} during deletion.")
            await db_client.table('projects').update({'sandbox': None}).eq('project_id', project_id).execute()
            return False

        if deleted_successfully:
            logger.info(f"Clearing sandbox info from DB for project {project_id} after successful deletion.")
            await db_client.table('projects').update({'sandbox': None}).eq('project_id', project_id).execute()
        else:
            logger.warning(f"Sandbox for project {project_id} (type: {sandbox_type}, id: {actual_sandbox_id}) might not have been deleted successfully. DB record not cleared.")

        return deleted_successfully

    except Exception as e:
        logger.error(f"Error in delete_sandbox for project {project_id}: {e}", exc_info=True)
        return False

