# Utility functions and constants for agent tools
from .document_generation_tool import DocumentGenerationTool

default_tools = [
    DocumentGenerationTool(),
]