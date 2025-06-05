
from typing import Optional

from ..agentpress.thread_manager import ThreadManager # Relative import
from ..agentpress.tool import Tool # Relative import
# Sandbox type can be Daytona's or our wrapper, so using Any for now, or a common base if defined
from typing import Any
from .sandbox import get_or_start_sandbox # Relative import
from ..utils.logger import logger # Relative import
from ..utils.files_utils import clean_path # Relative import
from ..utils.config import config # Relative import

class SandboxToolsBase(Tool):
    """Base class for all sandbox tools that provides project-based sandbox access."""
    
    # Class variable to track if sandbox URLs have been printed
    _urls_printed = False
    
    def __init__(self, project_id: str, thread_manager: Optional[ThreadManager] = None):
        super().__init__()
        self.project_id = project_id
        self.thread_manager = thread_manager
        self.workspace_path = "/workspace"
        self._sandbox: Optional[Any] = None # Can be Daytona Sandbox or LocalDockerSandboxWrapper
        self._sandbox_id: Optional[str] = None
        self._sandbox_pass: Optional[str] = None
        self.sandbox_type = config.get('SANDBOX_TYPE', 'daytona') # Store sandbox type

    async def _ensure_sandbox(self) -> Any: # Return type Any
        """Ensure we have a valid sandbox instance, retrieving it from the project if needed."""
        if self._sandbox is None:
            if self.thread_manager is None or self.thread_manager.db is None:
                logger.error("ThreadManager or DB client not available in SandboxToolsBase, cannot ensure sandbox.")
                raise ValueError("Database connection not available to ensure sandbox.")
            try:
                # Get database client
                client = await self.thread_manager.db.client # db_client is the supabase client instance
                
                # Project ID is already available as self.project_id
                # Get or start the sandbox using the updated signature
                self._sandbox = await get_or_start_sandbox(self.project_id, client) # Corrected call

                if self._sandbox is None:
                    # get_or_start_sandbox might return None if it fails internally
                    raise ValueError(f"Failed to get or start sandbox for project {self.project_id}")

                # Store sandbox id and pass if sandbox object is successfully retrieved
                # This assumes the sandbox object (Daytona or Wrapper) has an 'id' attribute
                # And we can fetch 'pass' from the DB again if needed, or if it's part of a wrapper.
                # For now, let's ensure self._sandbox_id is set from the sandbox object.
                self._sandbox_id = self._sandbox.id
                
                # Fetching pass again if necessary, though it's used by create_sandbox primarily.
                # If tools need the VNC pass, they might need to get it from the sandbox object if available,
                # or we query the DB here. For now, let's assume it's not directly needed by _ensure_sandbox's role.
                # project_result = await client.table('projects').select('sandbox').eq('project_id', self.project_id).maybe_single().execute()
                # if project_result.data and project_result.data.get('sandbox'):
                #     self._sandbox_pass = project_result.data['sandbox'].get('pass')

                # # Log URLs if not already printed
                # if not SandboxToolsBase._urls_printed and hasattr(self._sandbox, 'get_preview_link'):
                #     vnc_preview_info = self._sandbox.get_preview_link(6080) # dict for wrapper
                #     web_preview_info = self._sandbox.get_preview_link(8080) # dict for wrapper
                    
                #     vnc_url = vnc_preview_info.get('url') if isinstance(vnc_preview_info, dict) else (vnc_preview_info.url if hasattr(vnc_preview_info, 'url') else str(vnc_preview_info))
                #     web_url = web_preview_info.get('url') if isinstance(web_preview_info, dict) else (web_preview_info.url if hasattr(web_preview_info, 'url') else str(web_preview_info))
                    
                #     print("\033[95m***")
                #     print(f"VNC URL: {vnc_url}")
                #     print(f"Website URL: {web_url}")
                #     print("***\033[0m")
                #     SandboxToolsBase._urls_printed = True
                
            except Exception as e:
                logger.error(f"Error ensuring sandbox for project {self.project_id}: {str(e)}", exc_info=True)
                raise e # Re-raise after logging
        
        return self._sandbox

    @property
    def sandbox(self) -> Any: # Return type Any
        """Get the sandbox instance, ensuring it exists."""
        if self._sandbox is None:
            raise RuntimeError("Sandbox not initialized. Call _ensure_sandbox() first.")
        return self._sandbox

    @property
    def sandbox_id(self) -> str:
        """Get the sandbox ID, ensuring it exists."""
        if self._sandbox_id is None:
            raise RuntimeError("Sandbox ID not initialized. Call _ensure_sandbox() first.")
        return self._sandbox_id

    def clean_path(self, path: str) -> str:
        """Clean and normalize a path to be relative to /workspace."""
        cleaned_path = clean_path(path, self.workspace_path)
        logger.debug(f"Cleaned path: {path} -> {cleaned_path}")
        return cleaned_path