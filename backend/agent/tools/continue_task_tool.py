from agentpress.tool import Tool

TOOL_NAME = "continue_task"
TOOL_DESCRIPTION = """
Use this tool when you have completed a step in your plan and there are more steps to follow.
This will allow you to continue working on the next step of your plan without user intervention.
Only call this tool after you have successfully completed a step and are ready for the next one.
"""

class ContinueTaskTool(Tool):
    def __init__(self):
        super().__init__(TOOL_NAME, TOOL_DESCRIPTION)

    def run(self, **kwargs) -> str:
        # This tool doesn't need to return anything meaningful.
        # Its purpose is to signal the execution loop.
        return "Continuing to the next step."
