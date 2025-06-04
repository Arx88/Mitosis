# backend/agent/tools/continue_task_tool.py
# Asegúrate de que la importación de Tool y xml_schema sea desde la ubicación correcta.
# Basado en la estructura de tu proyecto, probablemente sea:
from agentpress.tool import Tool, xml_schema

TOOL_NAME = "continue_task"
TOOL_DESCRIPTION = """Use this tool when you have completed a step in your plan and there are more steps to follow. This will allow you to continue working on the next step of your plan without user intervention. Only call this tool after you have successfully completed a step and are ready for the next one."""

class ContinueTaskTool(Tool):
    # Estos atributos de clase son importantes para que ToolRegistry identifique la herramienta.
    name = TOOL_NAME
    description = TOOL_DESCRIPTION

    def __init__(self):
        super().__init__() # Llamada al constructor base sin argumentos.

    # AÑADIR EL DECORADOR @xml_schema AQUÍ
    @xml_schema(
        tag_name=TOOL_NAME,  # Esto define que el LLM usará <continue_task />
        mappings=[],         # No se esperan argumentos del LLM para esta herramienta
        example="<continue_task />" # Ejemplo de uso para el LLM
    )
    def run(self) -> str:
        """
        Signals the agent to continue with the next step in its plan.
        This tool is invoked without arguments from the LLM.
        """
        return "ContinueTaskTool executed: Signalling agent to proceed."
