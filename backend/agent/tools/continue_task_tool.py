from agentpress.tool import Tool

TOOL_NAME = "continue_task"
TOOL_DESCRIPTION = """
Use this tool when you have completed a step in your plan and there are more steps to follow.
This will allow you to continue working on the next step of your plan without user intervention.
Only call this tool after you have successfully completed a step and are ready for the next one.
"""

class ContinueTaskTool(Tool):
    def __init__(self):
        super().__init__() # Llamar al constructor de la clase base sin argumentos
        # TOOL_NAME y TOOL_DESCRIPTION pueden permanecer como constantes a nivel de módulo
        # o asignarse a self.name y self.description si fueran necesarios en otro lugar,
        # pero para resolver el TypeError, solo se necesita corregir la llamada a super.
        # Por simplicidad y dado que esta herramienta es especial, mantenerlos como constantes
        # del módulo está bien por ahora. Si se necesitara que la herramienta se muestre
        # en una UI de configuración, se podrían asignar aquí:
        # self.name = TOOL_NAME
        # self.description = TOOL_DESCRIPTION

    def run(self, **kwargs) -> str:
        # This tool doesn't need to return anything meaningful.
        # Its purpose is to signal the execution loop.
        return "Continuing to the next step."
