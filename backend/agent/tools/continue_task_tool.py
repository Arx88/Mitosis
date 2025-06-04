# backend/agent/tools/continue_task_tool.py
from agentpress.tool import Tool # Verificar que esta ruta de importación sea la correcta para la clase base Tool

TOOL_NAME = "continue_task"
TOOL_DESCRIPTION = """Use this tool when you have completed a step in your plan and there are more steps to follow. This will allow you to continue working on the next step of your plan without user intervention. Only call this tool after you have successfully completed a step and are ready for the next one."""

class ContinueTaskTool(Tool):
    # Estos atributos de clase son importantes para que ToolRegistry identifique la herramienta.
    name = TOOL_NAME
    description = TOOL_DESCRIPTION

    def __init__(self):
        super().__init__() # Llamada al constructor base sin argumentos.

    # Modificar la firma del método 'run' para que no acepte **kwargs.
    # Debe ser un método simple sin argumentos (aparte de 'self') para que
    # el sistema de introspección de la clase base 'Tool' pueda generar su esquema correctamente.
    def run(self) -> str:
        """
        Signals the agent to continue with the next step in its plan.
        This tool is invoked without arguments from the LLM.
        """
        return "ContinueTaskTool executed: Signalling agent to proceed."
