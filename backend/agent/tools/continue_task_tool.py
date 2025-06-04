# backend/agent/tools/continue_task_tool.py

# La IA debe usar la importación que se haya confirmado que funciona
# tanto para el backend como para el worker (probablemente sin 'backend.' al inicio):
from agentpress.tool import Tool, xml_schema

TOOL_NAME = "continue_task"
TOOL_DESCRIPTION = """Use this tool when you have completed a step in your plan and there are more steps to follow. This will allow you to continue working on the next step of your plan without user intervention. Only call this tool after you have successfully completed a step and are ready for the next one."""

class ContinueTaskTool(Tool):
    name = TOOL_NAME
    description = TOOL_DESCRIPTION

    def __init__(self):
        super().__init__()

    # ---- ESTE ES EL CAMBIO MÁS IMPORTANTE ----
    # Asegurar que el decorador @xml_schema esté presente y configurado así:
    @xml_schema(
        tag_name=TOOL_NAME,  # Para que el LLM pueda usar <continue_task />
        mappings=[],         # Indica que el método 'run' no espera argumentos del LLM
        example="<continue_task />"
    )
    def run(self) -> str:
        """
        Signals the agent to continue with the next step in its plan.
        This tool is invoked without arguments from the LLM.
        """
        return "ContinueTaskTool executed: Signalling agent to proceed."
