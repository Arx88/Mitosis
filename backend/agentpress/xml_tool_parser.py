import xml.etree.ElementTree as ET
from typing import List, Optional

from agentpress.tool import ToolCall


class XMLToolParser:
    """A parser for tool calls in XML format."""

    def parse(self, xml_string: str) -> Optional[List[ToolCall]]:
        """
        Parses a string of XML and returns a list of ToolCall objects.

        Args:
            xml_string: The string of XML to parse.

        Returns:
            A list of ToolCall objects, or None if the string is not valid XML.
        """
        try:
            # Envolvemos el string XML con una raíz ficticia para manejar múltiples herramientas
            # y la ausencia de un elemento raíz único.
            # Esto hace que el parser sea mucho más flexible.
            wrapped_xml_string = f"<dummy_root>{xml_string}</dummy_root>"
            root = ET.fromstring(wrapped_xml_string)

            tool_calls = []

            # El elemento raíz puede ser 'tools' o el ficticio 'dummy_root'
            # Iteramos sobre sus hijos, que son las verdaderas llamadas a herramientas
            for tool_element in root:
                tool_name = tool_element.tag
                tool_kwargs = {}
                for param_element in tool_element:
                    param_name = param_element.tag
                    param_value = param_element.text or ""
                    tool_kwargs[param_name] = param_value
                tool_calls.append(ToolCall(tool_name, tool_kwargs))

            return tool_calls
        except ET.ParseError as e:
            # Si incluso con el envoltorio falla, es un XML mal formado.
            # Podríamos registrar el error para depuración.
            print(f"Error al analizar XML: {e}")
            return None