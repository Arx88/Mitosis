import xml.etree.ElementTree as ET
from typing import List, Optional

# Ensure this import path is correct for your project structure
from agentpress.tool import ToolCall


class XMLToolParser:
    """Un analizador para llamadas a herramientas en formato XML."""

    def parse(self, xml_string: str) -> Optional[List[ToolCall]]:
        """
        Analiza una cadena de XML y devuelve una lista de objetos ToolCall.

        Este analizador es flexible y está diseñado para manejar múltiples formatos, incluyendo:
        1. Formato simple: <nombre_herramienta><param>valor</param></nombre_herramienta>
        2. Formato de invocación: <invoke name="nombre_herramienta"><parameter name="param">valor</parameter></invoke>
        También maneja múltiples llamadas a herramientas, ya sea que estén o no envueltas en un elemento raíz.
        """
        if not xml_string or not xml_string.strip():
            return []

        try:
            # Envolver el string en una raíz ficticia para manejar múltiples elementos raíz
            wrapped_xml_string = f"<dummy_root>{xml_string.strip()}</dummy_root>"
            root = ET.fromstring(wrapped_xml_string)

            tool_calls = []

            # --- This part needs to be more robust for nested containers ---
            temp_elements_to_check = list(root) # Start with children of dummy_root
            final_tool_elements = []

            while temp_elements_to_check:
                element = temp_elements_to_check.pop(0) # Get first element
                if element.tag.lower() in ['function_calls', 'tools', 'dummy_root']: # Added dummy_root just in case
                    # If it's a known container, add its children to the front of the list to be checked
                    temp_elements_to_check[0:0] = list(element)
                else:
                    # If it's not a known container, it's a potential tool element
                    final_tool_elements.append(element)
            # --- End of modified part ---

            for element in final_tool_elements:
                tool_name_val = None # Corrected variable name for clarity
                tool_kwargs_val = {} # Corrected variable name for clarity

                # Detectar el formato <invoke name="...">
                if element.tag.lower() == 'invoke':
                    tool_name_val = element.get('name')
                    for param_element in element:
                        if param_element.tag.lower() == 'parameter':
                            param_name = param_element.get('name')
                            param_value = param_element.text.strip() if param_element.text else ""
                            if param_name:
                                tool_kwargs_val[param_name] = param_value
                # Manejar el formato simple <tool_name>...</tool_name>
                else:
                    tool_name_val = element.tag
                    # Add attributes of the main tool tag as parameters
                    for attr_name, attr_value in element.attrib.items():
                        tool_kwargs_val[attr_name] = attr_value
                    # Add children elements as parameters
                    for param_element in element:
                        param_name = param_element.tag
                        param_value = param_element.text.strip() if param_element.text else ""
                        tool_kwargs_val[param_name] = param_value

                if tool_name_val:
                    # Corrected instantiation to match ToolCall dataclass
                    tool_calls.append(ToolCall(tool_name=tool_name_val, tool_kwargs=tool_kwargs_val))

            return tool_calls
        except ET.ParseError as e:
            # It's good practice to log the error or handle it appropriately
            # For now, printing as in user's example
            print(f"Error irrecuperable al analizar XML: {e}")
            return None
