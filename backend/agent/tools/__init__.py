from agentpress.tool import Tool
from .continue_task_tool import ContinueTaskTool
from .data_providers_tool import DataProvidersTool
from .document_generation_tool import SandboxDocumentGenerationTool
from .expand_msg_tool import ExpandMessageTool
from .message_tool import MessageTool
from .sb_browser_tool import ComputerUseTool
from .update_agent_tool import UpdateAgentTool
from .web_search_tool import WebSearchTool
# INICIO DE MODIFICACIÓN
from .deep_research_tool_updated import SandboxDeepResearchTool
from .website_creator_tool_updated import SandboxWebsiteCreatorTool
# FIN DE MODIFICACIÓN

default_tools: list[Tool] = [
    WebSearchTool(),
    ComputerUseTool(),
    ContinueTaskTool(),
    MessageTool(),
    UpdateAgentTool(),
    DataProvidersTool(),
    ExpandMessageTool(), # Corrected
    SandboxDocumentGenerationTool(), # Corrected
    # INICIO DE MODIFICACIÓN
    SandboxDeepResearchTool(),
    SandboxWebsiteCreatorTool(),
    # FIN DE MODIFICACIÓN
]

__all__ = ["default_tools", "Tool"]