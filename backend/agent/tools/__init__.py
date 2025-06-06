from agentpress.tool import Tool
from .continue_task_tool import ContinueTaskTool
from .data_providers_tool import DataProvidersTool
from .document_generation_tool import SandboxDocumentGenerationTool
from .expand_msg_tool import ExpandMessageTool
from .message_tool import MessageTool
from .sb_browser_tool import SandboxBrowserTool # Was ComputerUseTool
from .update_agent_tool import UpdateAgentTool
from .web_search_tool import SandboxWebSearchTool # Was WebSearchTool
from .deep_research_tool_updated import SandboxDeepResearchTool # New
from .website_creator_tool_updated import SandboxWebsiteCreatorTool # New

default_tools: list[Tool] = [
    SandboxWebSearchTool(),       # Corrected from WebSearchTool
    SandboxBrowserTool(),       # Corrected from ComputerUseTool
    ContinueTaskTool(),           # Correct
    MessageTool(),                # Correct
    DataProvidersTool(),          # Correct
    SandboxDocumentGenerationTool(),# Already Corrected
    SandboxDeepResearchTool(),    # New
    SandboxWebsiteCreatorTool(),  # New
]

__all__ = ["default_tools", "Tool"]