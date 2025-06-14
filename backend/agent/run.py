import os
import json
import re
import inspect
from uuid import uuid4
from typing import Optional

# from agent.tools.message_tool import MessageTool
from agent.tools.message_tool import MessageTool
from agent.tools.document_generation_tool import SandboxDocumentGenerationTool
from agent.tools.sb_deploy_tool import SandboxDeployTool
from agent.tools.sb_expose_tool import SandboxExposeTool
from agent.tools.web_search_tool import SandboxWebSearchTool
from agent.tools.deep_research_tool_updated import DeepResearchToolUpdated
from dotenv import load_dotenv
from utils.config import config

from agent.agent_builder_prompt import get_agent_builder_prompt
from agentpress.thread_manager import ThreadManager
from agentpress.response_processor import ProcessorConfig
from agent.tools.sb_shell_tool import SandboxShellTool
from agent.tools.sb_files_tool import SandboxFilesTool
from agent.tools.sb_browser_tool import SandboxBrowserTool
from agent.tools.data_providers_tool import DataProvidersTool
from agent.tools.expand_msg_tool import ExpandMessageTool
from agent.tools.continue_task_tool import ContinueTaskTool
from agent.prompt import get_system_prompt
from utils.logger import logger
from utils.auth_utils import get_account_id_from_thread
from services.billing import check_billing_status
from agent.tools.sb_vision_tool import SandboxVisionTool
from services.langfuse import langfuse
from langfuse.client import StatefulTraceClient
from services.langfuse import langfuse
from agent.gemini_prompt import get_gemini_system_prompt
from agent.tools.mcp_tool_wrapper import MCPToolWrapper
from agentpress.tool import SchemaType

load_dotenv()

async def run_agent(
    thread_id: str,
    project_id: str,
    stream: bool,
    thread_manager: Optional[ThreadManager] = None,
    native_max_auto_continues: int = 25,
    max_iterations: int = 100,
    model_name: str = "anthropic/claude-3-7-sonnet-latest",
    enable_thinking: Optional[bool] = False,
    reasoning_effort: Optional[str] = 'low',
    enable_context_manager: bool = True,
    agent_config: Optional[dict] = None,    
    trace: Optional[StatefulTraceClient] = None,
    is_agent_builder: Optional[bool] = False,
    target_agent_id: Optional[str] = None
):
    """Run the development agent with specified configuration."""
    logger.info(f"🚀 Starting agent with model: {model_name}")
    if agent_config:
        logger.info(f"Using custom agent: {agent_config.get('name', 'Unknown')}")

    if not trace:
        trace = langfuse.trace(name="run_agent", session_id=thread_id, metadata={"project_id": project_id})
    thread_manager = ThreadManager(trace=trace, is_agent_builder=is_agent_builder, target_agent_id=target_agent_id)

    client = await thread_manager.db.client

    # Get account ID from thread for billing checks
    account_id = await get_account_id_from_thread(client, thread_id)
    if not account_id:
        raise ValueError("Could not determine account ID for thread")

    # Get sandbox info from project
    project = await client.table('projects').select('*').eq('project_id', project_id).execute()
    if not project.data or len(project.data) == 0:
        raise ValueError(f"Project {project_id} not found")

    project_data = project.data[0]
    sandbox_info = project_data.get('sandbox', {})
    if not sandbox_info.get('id'):
        raise ValueError(f"No sandbox found for project {project_id}")

    # Initialize tools with project_id instead of sandbox object
    # This ensures each tool independently verifies it's operating on the correct project
    
    # Get enabled tools from agent config, or use defaults
    enabled_tools = None
    if agent_config and 'agentpress_tools' in agent_config:
        enabled_tools = agent_config['agentpress_tools']
        logger.info(f"Using custom tool configuration from agent")
    
    # Register tools based on configuration
    # If no agent config (enabled_tools is None), register ALL tools for full Suna capabilities
    # If agent config exists, only register explicitly enabled tools
    if is_agent_builder:
        logger.info("Agent builder mode - registering only update agent tool")
        from agent.tools.update_agent_tool import UpdateAgentTool
        from services.supabase import DBConnection
        db = DBConnection()
        thread_manager.add_tool(UpdateAgentTool, thread_manager=thread_manager, db_connection=db, agent_id=target_agent_id)

    if enabled_tools is None:
        # No agent specified - register ALL tools for full Suna experience
        logger.info("No agent specified - registering all tools for full Suna capabilities")
        thread_manager.add_tool(SandboxShellTool, project_id=project_id, thread_manager=thread_manager)
        thread_manager.add_tool(SandboxFilesTool, project_id=project_id, thread_manager=thread_manager)
        thread_manager.add_tool(SandboxBrowserTool, project_id=project_id, thread_id=thread_id, thread_manager=thread_manager)
        thread_manager.add_tool(SandboxDeployTool, project_id=project_id, thread_manager=thread_manager)
        thread_manager.add_tool(SandboxExposeTool, project_id=project_id, thread_manager=thread_manager)
        thread_manager.add_tool(ExpandMessageTool, thread_id=thread_id, thread_manager=thread_manager)
        thread_manager.add_tool(MessageTool)
        thread_manager.add_tool(ContinueTaskTool)
        thread_manager.add_tool(SandboxWebSearchTool, project_id=project_id, thread_manager=thread_manager)
        thread_manager.add_tool(SandboxVisionTool, project_id=project_id, thread_id=thread_id, thread_manager=thread_manager)
        thread_manager.add_tool(SandboxDocumentGenerationTool, project_id=project_id, thread_manager=thread_manager)
        thread_manager.add_tool(DeepResearchToolUpdated, project_id=project_id, thread_manager=thread_manager)
        if config.RAPID_API_KEY:
            thread_manager.add_tool(DataProvidersTool)
    else:
        logger.info("Custom agent specified - registering only enabled tools")
        logger.info(f"DEBUG: enabled_tools for custom agent: {enabled_tools}")
        thread_manager.add_tool(ExpandMessageTool, thread_id=thread_id, thread_manager=thread_manager)
        thread_manager.add_tool(MessageTool)
        thread_manager.add_tool(ContinueTaskTool)
        if enabled_tools.get('sb_shell_tool', {}).get('enabled', False):
            thread_manager.add_tool(SandboxShellTool, project_id=project_id, thread_manager=thread_manager)
        if enabled_tools.get('sb_files_tool', {}).get('enabled', False):
            thread_manager.add_tool(SandboxFilesTool, project_id=project_id, thread_manager=thread_manager)
        if enabled_tools.get('sb_browser_tool', {}).get('enabled', False):
            thread_manager.add_tool(SandboxBrowserTool, project_id=project_id, thread_id=thread_id, thread_manager=thread_manager)
        if enabled_tools.get('sb_deploy_tool', {}).get('enabled', False):
            thread_manager.add_tool(SandboxDeployTool, project_id=project_id, thread_manager=thread_manager)
        if enabled_tools.get('sb_expose_tool', {}).get('enabled', False):
            thread_manager.add_tool(SandboxExposeTool, project_id=project_id, thread_manager=thread_manager)
        if enabled_tools.get('web_search_tool', {}).get('enabled', False):
            thread_manager.add_tool(SandboxWebSearchTool, project_id=project_id, thread_manager=thread_manager)
        if enabled_tools.get('sb_vision_tool', {}).get('enabled', False):
            thread_manager.add_tool(SandboxVisionTool, project_id=project_id, thread_id=thread_id, thread_manager=thread_manager)
        if enabled_tools.get('sandbox_document_generation_tool', {}).get('enabled', False): # Note: Key might be 'sb_document_generation_tool' based on tools.ts
            thread_manager.add_tool(SandboxDocumentGenerationTool, project_id=project_id, thread_manager=thread_manager)
            logger.info("Registered SandboxDocumentGenerationTool for custom agent.")
        logger.info(f"DEBUG: Value of enabled_tools.get('DeepResearchToolUpdated', {{}}): {enabled_tools.get('DeepResearchToolUpdated', {})}")
        if enabled_tools.get('DeepResearchToolUpdated', {}).get('enabled', False): # Key changed back here
            thread_manager.add_tool(DeepResearchToolUpdated, project_id=project_id, thread_manager=thread_manager)
            logger.info("Registered DeepResearchToolUpdated for custom agent.")
        if config.RAPID_API_KEY and enabled_tools.get('data_providers_tool', {}).get('enabled', False):
            thread_manager.add_tool(DataProvidersTool)

    # Register MCP tool wrapper if agent has configured MCPs or custom MCPs
    mcp_wrapper_instance = None
    if agent_config:
        # Merge configured_mcps and custom_mcps
        all_mcps = []
        
        # Add standard configured MCPs
        if agent_config.get('configured_mcps'):
            all_mcps.extend(agent_config['configured_mcps'])
        
        # Add custom MCPs
        if agent_config.get('custom_mcps'):
            for custom_mcp in agent_config['custom_mcps']:
                # Transform custom MCP to standard format
                mcp_config = {
                    'name': custom_mcp['name'],
                    'qualifiedName': f"custom_{custom_mcp['type']}_{custom_mcp['name'].replace(' ', '_').lower()}",
                    'config': custom_mcp['config'],
                    'enabledTools': custom_mcp.get('enabledTools', []),
                    'isCustom': True,
                    'customType': custom_mcp['type']
                }
                all_mcps.append(mcp_config)
        
        if all_mcps:
            logger.info(f"Registering MCP tool wrapper for {len(all_mcps)} MCP servers (including {len(agent_config.get('custom_mcps', []))} custom)")
            # Register the tool with all MCPs
            thread_manager.add_tool(MCPToolWrapper, mcp_configs=all_mcps)
            
            # Get the tool instance from the registry
            # The tool is registered with method names as keys
            for tool_name, tool_info in thread_manager.tool_registry.tools.items():
                if isinstance(tool_info['instance'], MCPToolWrapper):
                    mcp_wrapper_instance = tool_info['instance']
                    break
            
            # Initialize the MCP tools asynchronously
            if mcp_wrapper_instance:
                try:
                    await mcp_wrapper_instance.initialize_and_register_tools()
                    logger.info("MCP tools initialized successfully")
                    
                    # Re-register the updated schemas with the tool registry
                    # This ensures the dynamically created tools are available for function calling
                    updated_schemas = mcp_wrapper_instance.get_schemas()
                    for method_name, schema_list in updated_schemas.items():
                        if method_name != 'call_mcp_tool':  # Skip the fallback method
                            # Register each dynamic tool in the registry
                            for schema in schema_list:
                                if schema.schema_type == SchemaType.OPENAPI:
                                    thread_manager.tool_registry.tools[method_name] = {
                                        "instance": mcp_wrapper_instance,
                                        "schema": schema
                                    }
                                    logger.debug(f"Registered dynamic MCP tool: {method_name}")
                
                except Exception as e:
                    logger.error(f"Failed to initialize MCP tools: {e}")
                    # Continue without MCP tools if initialization fails

    # Prepare system prompt
    # First, get the default system prompt
    if "gemini-2.5-flash" in model_name.lower():
        default_system_content = get_gemini_system_prompt()
    else:
        # Use the original prompt - the LLM can only use tools that are registered
        default_system_content = get_system_prompt()
        
    # Add sample response for non-anthropic models
    if "anthropic" not in model_name.lower():
        sample_response_path = os.path.join(os.path.dirname(__file__), 'sample_responses/1.txt')
        with open(sample_response_path, 'r') as file:
            sample_response = file.read()
        default_system_content = default_system_content + "\n\n <sample_assistant_response>" + sample_response + "</sample_assistant_response>"
    
    # Handle custom agent system prompt
    if agent_config and agent_config.get('system_prompt'):
        custom_system_prompt = agent_config['system_prompt'].strip()
        
        # Completely replace the default system prompt with the custom one
        # This prevents confusion and tool hallucination
        system_content = custom_system_prompt
        logger.info(f"Using ONLY custom agent system prompt for: {agent_config.get('name', 'Unknown')}")
    elif is_agent_builder:
        system_content = get_agent_builder_prompt()
        logger.info("Using agent builder system prompt")
    else:
        # Use just the default system prompt
        system_content = default_system_content
        logger.info("Using default system prompt only")
    
    # Add MCP tool information to system prompt if MCP tools are configured
    # Append descriptions of standard (non-MCP) enabled tools to the system_content
    standard_tools_info = "\n\n--- Other Available Tools ---\n"
    standard_tools_info += "You have access to the following tools. Use them by invoking their function name with parameters, like in the examples shown elsewhere in the prompt.\n"

    processed_tool_classes = set()
    if thread_manager and hasattr(thread_manager, 'tool_registry') and thread_manager.tool_registry:
        # Group methods by their parent tool instance to avoid repeating class descriptions
        tool_methods_grouped = {}
        for method_name, tool_data in thread_manager.tool_registry.tools.items():
            tool_instance = tool_data.get('instance')
            if tool_instance and not isinstance(tool_instance, MCPToolWrapper): # Exclude MCPToolWrapper
                tool_class_name = tool_instance.__class__.__name__
                if tool_class_name not in tool_methods_grouped:
                    tool_methods_grouped[tool_class_name] = {'instance': tool_instance, 'methods': []}

                # Check if the method has an OpenAPI schema
                for schema_obj in tool_data.get('schema_list', [tool_data.get('schema')]): # schema_list or schema
                    if schema_obj and schema_obj.schema_type == SchemaType.OPENAPI and schema_obj.schema.get('function'):
                        tool_methods_grouped[tool_class_name]['methods'].append(schema_obj.schema['function'])
                        break # Found OpenAPI schema for this method

        if not tool_methods_grouped:
            standard_tools_info += "No standard tools seem to be enabled or registered for you at the moment.\n"
        else:
            for tool_class_name, tool_data in tool_methods_grouped.items():
                tool_instance = tool_data['instance']
                class_description = inspect.getdoc(tool_instance) or "No description provided for this tool."

                # Only add tool class if it has callable methods with OpenAPI schemas
                if tool_data['methods']:
                    standard_tools_info += f"\n**Tool Class: {tool_class_name}**\n"
                    standard_tools_info += f"   Description: {class_description}\n"
                    standard_tools_info += f"   Available functions:\n"

                    for func_schema in tool_data['methods']:
                        func_name = func_schema.get('name', 'UnknownFunction')
                        func_description = func_schema.get('description', 'No function description.')
                        # ADD LOGGING HERE
                        if func_name == 'deep-search' or tool_class_name == 'DeepResearchToolUpdated':
                            logger.info(f"DEBUG_PROMPT_GEN: For {tool_class_name}.{func_name}, schema being added to prompt: {func_schema}")
                        standard_tools_info += f"     - `{func_name}`: {func_description}\n"

                        params = func_schema.get('parameters', {}).get('properties', {})
                        if params:
                            param_details = []
                            for param_name, param_info in params.items():
                                param_desc = param_info.get('description', '')
                                param_type = param_info.get('type', 'any')
                                detail = f"{param_name} ({param_type})"
                                if param_desc:
                                    detail += f": {param_desc}"
                                param_details.append(detail)
                            if param_details:
                                standard_tools_info += f"       Parameters: {'; '.join(param_details)}\n"
                        required_params = func_schema.get('parameters', {}).get('required', [])
                        if required_params:
                            standard_tools_info += f"       Required: {', '.join(required_params)}\n"
    else:
        standard_tools_info += "Tool registry not available or no tools registered.\n"

    # Append this information to the system_content
    # This ensures it's added regardless of whether a custom or default prompt is used.
    # We check if it's not already there to prevent massive duplication if run_agent is somehow re-entered (defensive)
    if "--- Other Available Tools ---" not in system_content:
        system_content += standard_tools_info
        logger.info("Appended standard tool descriptions to the system prompt.")

    if agent_config and (agent_config.get('configured_mcps') or agent_config.get('custom_mcps')) and mcp_wrapper_instance and mcp_wrapper_instance._initialized:
        mcp_info = "\n\n--- MCP Tools Available ---\n"
        mcp_info += "You have access to external MCP (Model Context Protocol) server tools.\n"
        mcp_info += "MCP tools can be called directly using their native function names in the standard function calling format:\n"
        mcp_info += '<function_calls>\n'
        mcp_info += '<invoke name="{tool_name}">\n'
        mcp_info += '<parameter name="param1">value1</parameter>\n'
        mcp_info += '<parameter name="param2">value2</parameter>\n'
        mcp_info += '</invoke>\n'
        mcp_info += '</function_calls>\n\n'
        
        # List available MCP tools
        mcp_info += "Available MCP tools:\n"
        try:
            # Get the actual registered schemas from the wrapper
            registered_schemas = mcp_wrapper_instance.get_schemas()
            for method_name, schema_list in registered_schemas.items():
                if method_name == 'call_mcp_tool':
                    continue  # Skip the fallback method
                    
                # Get the schema info
                for schema in schema_list:
                    if schema.schema_type == SchemaType.OPENAPI:
                        func_info = schema.schema.get('function', {})
                        description = func_info.get('description', 'No description available')
                        # Extract server name from description if available
                        server_match = description.find('(MCP Server: ')
                        if server_match != -1:
                            server_end = description.find(')', server_match)
                            server_info = description[server_match:server_end+1]
                        else:
                            server_info = ''
                        
                        mcp_info += f"- **{method_name}**: {description}\n"
                        
                        # Show parameter info
                        params = func_info.get('parameters', {})
                        props = params.get('properties', {})
                        if props:
                            mcp_info += f"  Parameters: {', '.join(props.keys())}\n"
                            
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}")
            mcp_info += "- Error loading MCP tool list\n"
        
        # Add critical instructions for using search results
        mcp_info += "\n🚨 CRITICAL MCP TOOL RESULT INSTRUCTIONS 🚨\n"
        mcp_info += "When you use ANY MCP (Model Context Protocol) tools:\n"
        mcp_info += "1. ALWAYS read and use the EXACT results returned by the MCP tool\n"
        mcp_info += "2. For search tools: ONLY cite URLs, sources, and information from the actual search results\n"
        mcp_info += "3. For any tool: Base your response entirely on the tool's output - do NOT add external information\n"
        mcp_info += "4. DO NOT fabricate, invent, hallucinate, or make up any sources, URLs, or data\n"
        mcp_info += "5. If you need more information, call the MCP tool again with different parameters\n"
        mcp_info += "6. When writing reports/summaries: Reference ONLY the data from MCP tool results\n"
        mcp_info += "7. If the MCP tool doesn't return enough information, explicitly state this limitation\n"
        mcp_info += "8. Always double-check that every fact, URL, and reference comes from the MCP tool output\n"
        mcp_info += "\nIMPORTANT: MCP tool results are your PRIMARY and ONLY source of truth for external data!\n"
        mcp_info += "NEVER supplement MCP results with your training data or make assumptions beyond what the tools provide.\n"
        
        system_content += mcp_info
    
    system_message = { "role": "system", "content": system_content }

    iteration_count = 0
    continue_execution = True
    last_tool_name = ""

    latest_user_message = await client.table('messages').select('*').eq('thread_id', thread_id).eq('type', 'user').order('created_at', desc=True).limit(1).execute()
    if latest_user_message.data and len(latest_user_message.data) > 0:
        data = json.loads(latest_user_message.data[0]['content'])
        trace.update(input=data['content'])

    while continue_execution and iteration_count < max_iterations:
        iteration_count += 1
        last_tool_name = "" # Reset at the start of each iteration
        logger.info(f"🔄 Running iteration {iteration_count} of {max_iterations}...")

        # Billing check on each iteration - still needed within the iterations
        can_run, message, subscription = await check_billing_status(client, account_id)
        if not can_run:
            error_msg = f"Billing limit reached: {message}"
            trace.event(name="billing_limit_reached", level="ERROR", status_message=(f"{error_msg}"))
            error_data = {"type": "error", "message": error_msg}
            if stream:
                yield error_data
            else:
                yield {
                    "type": "status",
                    "status": "stopped",
                    "message": error_msg
                }
            break
        # Check if last message is from assistant using direct Supabase query
        latest_message = await client.table('messages').select('*').eq('thread_id', thread_id).in_('type', ['assistant', 'tool', 'user']).order('created_at', desc=True).limit(1).execute()
        if latest_message.data and len(latest_message.data) > 0:
            message_type = latest_message.data[0].get('type')
            if message_type == 'assistant':
                logger.info(f"Last message was from assistant, stopping execution")
                trace.event(name="last_message_from_assistant", level="DEFAULT", status_message=(f"Last message was from assistant, stopping execution"))
                continue_execution = False
                break

        # ---- Temporary Message Handling (Browser State & Image Context) ----
        temporary_message = None
        temp_message_content_list = [] # List to hold text/image blocks

        # Get the latest browser_state message
        latest_browser_state_msg = await client.table('messages').select('*').eq('thread_id', thread_id).eq('type', 'browser_state').order('created_at', desc=True).limit(1).execute()
        if latest_browser_state_msg.data and len(latest_browser_state_msg.data) > 0:
            try:
                raw_browser_content = latest_browser_state_msg.data[0]["content"]
                if isinstance(raw_browser_content, str):
                    logger.debug("Browser state content is a string, attempting to parse as JSON.")
                    browser_content = json.loads(raw_browser_content)
                elif isinstance(raw_browser_content, dict):
                    logger.debug("Browser state content is already a dictionary, using directly.")
                    browser_content = raw_browser_content
                else:
                    logger.warning(f"Browser state content is of unexpected type: {type(raw_browser_content)}. Attempting to use as is, but may cause issues.")
                    browser_content = raw_browser_content # Or handle as an error / default to empty dict

                screenshot_base64 = browser_content.get("screenshot_base64")
                screenshot_url = browser_content.get("screenshot_url")
                
                # Create a copy of the browser state without screenshot data
                browser_state_text = browser_content.copy()
                browser_state_text.pop('screenshot_base64', None)
                browser_state_text.pop('screenshot_url', None)

                if browser_state_text:
                    temp_message_content_list.append({
                        "type": "text",
                        "text": f"The following is the current state of the browser:\n{json.dumps(browser_state_text, indent=2)}"
                    })
                    
                # Prioritize screenshot_url if available
                if screenshot_url:
                    temp_message_content_list.append({
                        "type": "image_url",
                        "image_url": {
                            "url": screenshot_url,
                        }
                    })
                elif screenshot_base64:
                    # Fallback to base64 if URL not available
                    temp_message_content_list.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{screenshot_base64}",
                        }
                    })
                else:
                    logger.warning("Browser state found but no screenshot data.")

            except Exception as e:
                logger.error(f"Error parsing browser state: {e}")
                trace.event(name="error_parsing_browser_state", level="ERROR", status_message=(f"{e}"))

        # Get the latest image_context message (NEW)
        latest_image_context_msg = await client.table('messages').select('*').eq('thread_id', thread_id).eq('type', 'image_context').order('created_at', desc=True).limit(1).execute()
        if latest_image_context_msg.data and len(latest_image_context_msg.data) > 0:
            try:
                image_context_content = json.loads(latest_image_context_msg.data[0]["content"])
                base64_image = image_context_content.get("base64")
                mime_type = image_context_content.get("mime_type")
                file_path = image_context_content.get("file_path", "unknown file")

                if base64_image and mime_type:
                    temp_message_content_list.append({
                        "type": "text",
                        "text": f"Here is the image you requested to see: '{file_path}'"
                    })
                    temp_message_content_list.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                        }
                    })
                else:
                    logger.warning(f"Image context found for '{file_path}' but missing base64 or mime_type.")

                await client.table('messages').delete().eq('message_id', latest_image_context_msg.data[0]["message_id"]).execute()
            except Exception as e:
                logger.error(f"Error parsing image context: {e}")
                trace.event(name="error_parsing_image_context", level="ERROR", status_message=(f"{e}"))

        # If we have any content, construct the temporary_message
        if temp_message_content_list:
            temporary_message = {"role": "user", "content": temp_message_content_list}
            # logger.debug(f"Constructed temporary message with {len(temp_message_content_list)} content blocks.")
        # ---- End Temporary Message Handling ----

        # Set max_tokens based on model
        max_tokens = None
        if "sonnet" in model_name.lower():
            max_tokens = 64000
        elif "gpt-4" in model_name.lower():
            max_tokens = 4096
            
        generation = trace.generation(name="thread_manager.run_thread")
        try:
            # Make the LLM call and process the response
            response = await thread_manager.run_thread(
                thread_id=thread_id,
                system_prompt=system_message,
                stream=stream,
                llm_model=model_name,
                llm_temperature=0,
                llm_max_tokens=max_tokens,
                tool_choice="auto",
                max_xml_tool_calls=10,
                temporary_message=temporary_message,
                processor_config=ProcessorConfig(
                    xml_tool_calling=True,
                    native_tool_calling=False,
                    execute_tools=True,
                    execute_on_stream=True,
                    tool_execution_strategy="parallel",
                    xml_adding_strategy="user_message"
                ),
                native_max_auto_continues=native_max_auto_continues,
                include_xml_examples=True,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
                enable_context_manager=enable_context_manager,
                generation=generation
            )

            if isinstance(response, dict) and "status" in response and response["status"] == "error":
                logger.error(f"Error response from run_thread: {response.get('message', 'Unknown error')}")
                trace.event(name="error_response_from_run_thread", level="ERROR", status_message=(f"{response.get('message', 'Unknown error')}"))
                yield response
                break

            # Track if we see ask, complete, or web-browser-takeover tool calls
            last_tool_call = None
            agent_should_terminate = False

            # Process the response
            error_detected = False
            try:
                full_response = ""
                async for chunk in response:
                    if stream:
                        # If we receive an error chunk, we should stop after this iteration
                        if isinstance(chunk, dict) and chunk.get('type') == 'status' and chunk.get('status') == 'error':
                            logger.error(f"Error chunk detected: {chunk.get('message', 'Unknown error')}")
                            trace.event(name="error_chunk_detected", level="ERROR", status_message=(f"{chunk.get('message', 'Unknown error')}"))
                            error_detected = True
                            error_data = {"type": "error", "message": chunk.get('message', 'Unknown error from stream')}
                            yield error_data
                            continue     # Continue processing other chunks but don't break yet

                        # Check for termination signal and capture last_tool_name in status messages
                        if chunk.get('type') == 'status':
                            try:
                                content_str = chunk.get('content', '{}')
                                if isinstance(content_str, str):
                                    content = json.loads(content_str)
                                else:
                                    content = content_str

                                status_type = content.get('status_type')
                                tool_name = content.get('function_name') or content.get('xml_tag_name')

                                if status_type == 'tool_started' and tool_name:
                                    last_tool_name = tool_name
                                    tool_call_data = {"type": "tool_call", "tool_name": tool_name, "tool_args": content.get('arguments', {})}
                                    yield tool_call_data
                                elif status_type == 'tool_completed' and tool_name:
                                    last_tool_name = tool_name
                                    tool_result_data = {"type": "tool_result", "tool_name": tool_name, "tool_output": content.get('result', str(content)), "is_error": False}
                                    yield tool_result_data
                                elif status_type in ['tool_failed', 'tool_error'] and tool_name:
                                    last_tool_name = tool_name
                                    tool_result_data = {"type": "tool_result", "tool_name": tool_name, "tool_output": content.get('error_message', str(content)), "is_error": True}
                                    yield tool_result_data

                                # Parse the metadata to check for termination signal (ask/complete)
                                metadata = chunk.get('metadata', {})
                                if isinstance(metadata, str):
                                    metadata = json.loads(metadata)

                                if metadata.get('agent_should_terminate'):
                                    agent_should_terminate = True
                                    logger.info("Agent termination signal detected in status message (ask/complete tool used)")
                                    trace.event(name="agent_termination_signal_detected", level="DEFAULT", status_message="Agent termination signal detected in status message")
                                    if content.get('function_name'):
                                        last_tool_call = content['function_name']
                                    elif content.get('xml_tag_name'):
                                        last_tool_call = content['xml_tag_name']

                            except Exception as e:
                                logger.debug(f"Error parsing status message for SSE streaming: {e}")
                            # Do not yield the original status chunk if stream is True

                        # Check for XML versions like <ask>, <complete>, or <web-browser-takeover> in assistant content chunks
                        elif chunk.get('type') == 'assistant' and 'content' in chunk:
                            try:
                                content_str = chunk.get('content', '{}')
                                if isinstance(content_str, str):
                                    assistant_content_json = json.loads(content_str)
                                else:
                                    assistant_content_json = content_str

                                assistant_text = assistant_content_json.get('content', '')
                                if assistant_text: # Only yield if there's text
                                    thought_data = {"type": "thought", "content": assistant_text}
                                    yield thought_data

                                full_response += assistant_text # Accumulate for final response

                                if isinstance(assistant_text, str):
                                    if '</ask>' in assistant_text or '</complete>' in assistant_text or '</web-browser-takeover>' in assistant_text:
                                       if '</ask>' in assistant_text: xml_tool = 'ask'
                                       elif '</complete>' in assistant_text: xml_tool = 'complete'
                                       elif '</web-browser-takeover>' in assistant_text: xml_tool = 'web-browser-takeover'
                                       last_tool_call = xml_tool # This signals termination
                                       # agent_should_terminate will be set by metadata from these tools
                                       logger.info(f"Agent used XML tool: {xml_tool}")
                                       trace.event(name="agent_used_xml_tool", level="DEFAULT", status_message=(f"Agent used XML tool: {xml_tool}"))
                            except json.JSONDecodeError:
                                logger.warning(f"Warning: Could not parse assistant content JSON for SSE: {chunk.get('content')}")
                                trace.event(name="warning_could_not_parse_assistant_content_json_sse", level="WARNING", status_message=(f"Warning: Could not parse assistant content JSON for SSE: {chunk.get('content')}"))
                            except Exception as e:
                                logger.error(f"Error processing assistant chunk for SSE: {e}")
                                trace.event(name="error_processing_assistant_chunk_sse", level="ERROR", status_message=(f"Error processing assistant chunk for SSE: {e}"))
                            # Do not yield original assistant chunk if stream is True

                        elif chunk.get('type') == 'tool': # This is where actual tool results are often yielded by AgentPress
                            try:
                                metadata = chunk.get('metadata', {})
                                if isinstance(metadata, str): metadata = json.loads(metadata)

                                parsing_details = metadata.get('parsing_details', {})
                                tool_name_from_details = parsing_details.get('xml_tag_name')
                                # If not in details, try to get from the tool_execution_id in metadata if that's a pattern
                                # For now, relying on xml_tag_name from parsing_details.
                                tool_name = tool_name_from_details or last_tool_name # Fallback to last_tool_name if not in details

                                content_str_tool = chunk.get('content', '{}')
                                if isinstance(content_str_tool, str): content_json_tool = json.loads(content_str_tool)
                                else: content_json_tool = content_str_tool

                                actual_tool_output = content_json_tool.get('content', '')
                                is_error = content_json_tool.get('is_error', False) # Check if 'is_error' is part of the content

                                tool_result_data = {"type": "tool_result", "tool_name": tool_name, "tool_output": actual_tool_output, "is_error": is_error}
                                yield tool_result_data
                            except Exception as e:
                                logger.error(f"Error processing tool chunk for SSE: {e}")
                                # Potentially yield an error event here if appropriate
                            # Do not yield original tool chunk if stream is True

                        else: # Fallback for unknown chunk types if stream is True
                            # Decide if these should be errors, thoughts, or ignored. For now, ignoring.
                            logger.warning(f"Unhandled chunk type during SSE streaming: {chunk.get('type')}")
                            # If you want to forward them anyway (not recommended for strict SSE):
                            # unknown_data = {"type": "unknown", "content": str(chunk)}
                            # yield f"data: {json.dumps(unknown_data)}\n\n"

                    else: # if not stream
                        # Original behavior: just yield the chunk
                        # Error detection for non-stream mode
                        if isinstance(chunk, dict) and chunk.get('type') == 'status' and chunk.get('status') == 'error':
                            logger.error(f"Error chunk detected (non-stream): {chunk.get('message', 'Unknown error')}")
                            trace.event(name="error_chunk_detected_non_stream", level="ERROR", status_message=(f"{chunk.get('message', 'Unknown error')}"))
                            error_detected = True

                        # Status message parsing for non-stream (mostly for agent_should_terminate)
                        if chunk.get('type') == 'status':
                            try:
                                content_str = chunk.get('content', '{}')
                                content = json.loads(content_str) if isinstance(content_str, str) else content_str
                                status_type = content.get('status_type')
                                if status_type in ['tool_started', 'tool_completed', 'tool_failed', 'tool_error']:
                                    tool_name = content.get('function_name') or content.get('xml_tag_name')
                                    if tool_name: last_tool_name = tool_name
                                metadata = chunk.get('metadata', {})
                                if isinstance(metadata, str): metadata = json.loads(metadata)
                                if metadata.get('agent_should_terminate'): agent_should_terminate = True
                            except Exception: pass # Ignore parsing errors for non-stream status

                        # Assistant content parsing for non-stream (full_response and agent_should_terminate)
                        if chunk.get('type') == 'assistant' and 'content' in chunk:
                            try:
                                content_str = chunk.get('content', '{}')
                                assistant_content_json = json.loads(content_str) if isinstance(content_str, str) else content_str
                                assistant_text = assistant_content_json.get('content', '')
                                full_response += assistant_text
                                if isinstance(assistant_text, str):
                                    if '</ask>' in assistant_text or '</complete>' in assistant_text or '</web-browser-takeover>' in assistant_text:
                                       xml_tool = 'ask' if '</ask>' in assistant_text else 'complete' if '</complete>' in assistant_text else 'web-browser-takeover'
                                       last_tool_call = xml_tool
                                       # agent_should_terminate is usually set by metadata with these tools
                            except Exception: pass # Ignore parsing errors for non-stream assistant

                        yield chunk # Original yield for non-streaming

                # NUEVA LÓGICA MÁS ROBUSTA Y SENCILLA ( wspólna dla stream i non-stream)
                if error_detected: # This error_detected flag is set by both stream/non-stream paths
                    logger.info(f"Stopping due to error detected in response stream for iteration {iteration_count}.")
                    trace.event(name="stopping_due_to_error_detected_in_response", level="DEFAULT", status_message=(f"Stopping due to error detected in response stream for iteration {iteration_count}."))
                    generation.end(output=full_response, status_message="error_detected_in_stream", level="ERROR")
                    continue_execution = False
                elif agent_should_terminate:
                    logger.info(f"Agent is stopping in iteration {iteration_count} because 'ask' or 'complete' tool was used (last_tool_name: {last_tool_name}).")
                    if stream: # Yield final response if streaming
                        final_response_data = {"type": "final_response", "content": full_response}
                        yield final_response_data
                    trace.event(name="agent_terminated_by_ask_or_complete", level="DEFAULT", status_message=(f"Agent stopped with tool: {last_tool_name}"))
                    generation.end(output=full_response, status_message="agent_stopped_ask_complete")
                    continue_execution = False
                else:
                    logger.info(f"Agent finished iteration {iteration_count} with tool '{last_tool_name}'. Continuing to next iteration.")
                    trace.event(name="agent_iteration_complete_continue", level="DEFAULT", status_message=(f"Agent continuing after tool: {last_tool_name}"))
                    generation.end(output=full_response, status_message=f"agent_continued_ok_last_tool:{last_tool_name}")

            except Exception as e:
                error_msg = f"Error during response streaming: {str(e)}"
                logger.error(f"Error: {error_msg}")
                trace.event(name="error_during_response_streaming", level="ERROR", status_message=(f"Error during response streaming: {str(e)}"))
                generation.end(output=full_response, status_message=error_msg, level="ERROR")
                error_data = {"type": "error", "message": error_msg}
                if stream:
                    yield error_data
                else:
                    yield { "type": "status", "status": "error", "message": error_msg } # Keep original format for non-stream
                break
                
        except Exception as e:
            error_msg = f"Error running thread: {str(e)}"
            logger.error(f"Error: {error_msg}")
            trace.event(name="error_running_thread", level="ERROR", status_message=(f"Error running thread: {str(e)}"))
            error_data = {"type": "error", "message": error_msg}
            if stream:
                yield error_data
            else:
                yield { "type": "status", "status": "error", "message": error_msg } # Keep original format for non-stream
            break
        # generation.end(output=full_response) # This was here, but it seems more logical to end it inside the try/except for streaming
                                            # For non-streaming, it's still valid.
                                            # For streaming, generation.end is called before breaking or continuing.
                                            # Let's ensure it's always called if generation started.
        if not generation.end_time: # Check if it hasn't been ended yet
            generation.end(output=full_response)


    langfuse.flush() # Flush Langfuse events at the end of the run
  


# # TESTING

# async def test_agent():
#     """Test function to run the agent with a sample query"""
#     from agentpress.thread_manager import ThreadManager
#     from services.supabase import DBConnection

#     # Initialize ThreadManager
#     thread_manager = ThreadManager()

#     # Create a test thread directly with Postgres function
#     client = await DBConnection().client

#     try:
#         # Get user's personal account
#         account_result = await client.rpc('get_personal_account').execute()

#         # if not account_result.data:
#         #     print("Error: No personal account found")
#         #     return

#         account_id = "a5fe9cb6-4812-407e-a61c-fe95b7320c59"

#         if not account_id:
#             print("Error: Could not get account ID")
#             return

#         # Find or create a test project in the user's account
#         project_result = await client.table('projects').select('*').eq('name', 'test11').eq('account_id', account_id).execute()

#         if project_result.data and len(project_result.data) > 0:
#             # Use existing test project
#             project_id = project_result.data[0]['project_id']
#             print(f"\n🔄 Using existing test project: {project_id}")
#         else:
#             # Create new test project if none exists
#             project_result = await client.table('projects').insert({
#                 "name": "test11",
#                 "account_id": account_id
#             }).execute()
#             project_id = project_result.data[0]['project_id']
#             print(f"\n✨ Created new test project: {project_id}")

#         # Create a thread for this project
#         thread_result = await client.table('threads').insert({
#             'project_id': project_id,
#             'account_id': account_id
#         }).execute()
#         thread_data = thread_result.data[0] if thread_result.data else None

#         if not thread_data:
#             print("Error: No thread data returned")
#             return

#         thread_id = thread_data['thread_id']
#     except Exception as e:
#         print(f"Error setting up thread: {str(e)}")
#         return

#     print(f"\n🤖 Agent Thread Created: {thread_id}\n")

#     # Interactive message input loop
#     while True:
#         # Get user input
#         user_message = input("\n💬 Enter your message (or 'exit' to quit): ")
#         if user_message.lower() == 'exit':
#             break

#         if not user_message.strip():
#             print("\n🔄 Running agent...\n")
#             await process_agent_response(thread_id, project_id, thread_manager)
#             continue

#         # Add the user message to the thread
#         await thread_manager.add_message(
#             thread_id=thread_id,
#             type="user",
#             content={
#                 "role": "user",
#                 "content": user_message
#             },
#             is_llm_message=True
#         )

#         print("\n🔄 Running agent...\n")
#         await process_agent_response(thread_id, project_id, thread_manager)

#     print("\n👋 Test completed. Goodbye!")

# async def process_agent_response(
#     thread_id: str,
#     project_id: str,
#     thread_manager: ThreadManager,
#     stream: bool = True,
#     model_name: str = "anthropic/claude-3-7-sonnet-latest",
#     enable_thinking: Optional[bool] = False,
#     reasoning_effort: Optional[str] = 'low',
#     enable_context_manager: bool = True
# ):
#     """Process the streaming response from the agent."""
#     chunk_counter = 0
#     current_response = ""
#     tool_usage_counter = 0 # Renamed from tool_call_counter as we track usage via status

#     # Create a test sandbox for processing with a unique test prefix to avoid conflicts with production sandboxes
#     sandbox_pass = str(uuid4())
#     sandbox = create_sandbox(sandbox_pass)

#     # Store the original ID so we can refer to it
#     original_sandbox_id = sandbox.id

#     # Generate a clear test identifier
#     test_prefix = f"test_{uuid4().hex[:8]}_"
#     logger.info(f"Created test sandbox with ID {original_sandbox_id} and test prefix {test_prefix}")

#     # Log the sandbox URL for debugging
#     print(f"\033[91mTest sandbox created: {str(sandbox.get_preview_link(6080))}/vnc_lite.html?password={sandbox_pass}\033[0m")

#     async for chunk in run_agent(
#         thread_id=thread_id,
#         project_id=project_id,
#         sandbox=sandbox,
#         stream=stream,
#         thread_manager=thread_manager,
#         native_max_auto_continues=25,
#         model_name=model_name,
#         enable_thinking=enable_thinking,
#         reasoning_effort=reasoning_effort,
#         enable_context_manager=enable_context_manager
#     ):
#         chunk_counter += 1
#         # print(f"CHUNK: {chunk}") # Uncomment for debugging

#         if chunk.get('type') == 'assistant':
#             # Try parsing the content JSON
#             try:
#                 # Handle content as string or object
#                 content = chunk.get('content', '{}')
#                 if isinstance(content, str):
#                     content_json = json.loads(content)
#                 else:
#                     content_json = content

#                 actual_content = content_json.get('content', '')
#                 # Print the actual assistant text content as it comes
#                 if actual_content:
#                      # Check if it contains XML tool tags, if so, print the whole tag for context
#                     if '<' in actual_content and '>' in actual_content:
#                          # Avoid printing potentially huge raw content if it's not just text
#                          if len(actual_content) < 500: # Heuristic limit
#                             print(actual_content, end='', flush=True)
#                          else:
#                              # Maybe just print a summary if it's too long or contains complex XML
#                              if '</ask>' in actual_content: print("<ask>...</ask>", end='', flush=True)
#                              elif '</complete>' in actual_content: print("<complete>...</complete>", end='', flush=True)
#                              else: print("<tool_call>...</tool_call>", end='', flush=True) # Generic case
#                     else:
#                         # Regular text content
#                          print(actual_content, end='', flush=True)
#                     current_response += actual_content # Accumulate only text part
#             except json.JSONDecodeError:
#                  # If content is not JSON (e.g., just a string chunk), print directly
#                  raw_content = chunk.get('content', '')
#                  print(raw_content, end='', flush=True)
#                  current_response += raw_content
#             except Exception as e:
#                  print(f"\nError processing assistant chunk: {e}\n")

#         elif chunk.get('type') == 'tool': # Updated from 'tool_result'
#             # Add timestamp and format tool result nicely
#             tool_name = "UnknownTool" # Try to get from metadata if available
#             result_content = "No content"

#             # Parse metadata - handle both string and dict formats
#             metadata = chunk.get('metadata', {})
#             if isinstance(metadata, str):
#                 try:
#                     metadata = json.loads(metadata)
#                 except json.JSONDecodeError:
#                     metadata = {}

#             linked_assistant_msg_id = metadata.get('assistant_message_id')
#             parsing_details = metadata.get('parsing_details')
#             if parsing_details:
#                 tool_name = parsing_details.get('xml_tag_name', 'UnknownTool') # Get name from parsing details

#             try:
#                 # Content is a JSON string or object
#                 content = chunk.get('content', '{}')
#                 if isinstance(content, str):
#                     content_json = json.loads(content)
#                 else:
#                     content_json = content

#                 # The actual tool result is nested inside content.content
#                 tool_result_str = content_json.get('content', '')
#                  # Extract the actual tool result string (remove outer <tool_result> tag if present)
#                 match = re.search(rf'<{tool_name}>(.*?)</{tool_name}>', tool_result_str, re.DOTALL)
#                 if match:
#                     result_content = match.group(1).strip()
#                     # Try to parse the result string itself as JSON for pretty printing
#                     try:
#                         result_obj = json.loads(result_content)
#                         result_content = json.dumps(result_obj, indent=2)
#                     except json.JSONDecodeError:
#                          # Keep as string if not JSON
#                          pass
#                 else:
#                      # Fallback if tag extraction fails
#                      result_content = tool_result_str

#             except json.JSONDecodeError:
#                 result_content = chunk.get('content', 'Error parsing tool content')
#             except Exception as e:
#                 result_content = f"Error processing tool chunk: {e}"

#             print(f"\n\n🛠️  TOOL RESULT [{tool_name}] → {result_content}")

#         elif chunk.get('type') == 'status':
#             # Log tool status changes
#             try:
#                 # Handle content as string or object
#                 status_content = chunk.get('content', '{}')
#                 if isinstance(status_content, str):
#                     status_content = json.loads(status_content)

#                 status_type = status_content.get('status_type')
#                 function_name = status_content.get('function_name', '')
#                 xml_tag_name = status_content.get('xml_tag_name', '') # Get XML tag if available
#                 tool_name = xml_tag_name or function_name # Prefer XML tag name

#                 if status_type == 'tool_started' and tool_name:
#                     tool_usage_counter += 1
#                     print(f"\n⏳ TOOL STARTING #{tool_usage_counter} [{tool_name}]")
#                     print("  " + "-" * 40)
#                     # Return to the current content display
#                     if current_response:
#                         print("\nContinuing response:", flush=True)
#                         print(current_response, end='', flush=True)
#                 elif status_type == 'tool_completed' and tool_name:
#                      status_emoji = "✅"
#                      print(f"\n{status_emoji} TOOL COMPLETED: {tool_name}")
#                 elif status_type == 'finish':
#                      finish_reason = status_content.get('finish_reason', '')
#                      if finish_reason:
#                          print(f"\n📌 Finished: {finish_reason}")
#                 # else: # Print other status types if needed for debugging
#                 #    print(f"\nℹ️ STATUS: {chunk.get('content')}")

#             except json.JSONDecodeError:
#                  print(f"\nWarning: Could not parse status content JSON: {chunk.get('content')}")
#             except Exception as e:
#                 print(f"\nError processing status chunk: {e}")


#         # Removed elif chunk.get('type') == 'tool_call': block

#     # Update final message
#     print(f"\n\n✅ Agent run completed with {tool_usage_counter} tool executions")

#     # Try to clean up the test sandbox if possible
#     try:
#         # Attempt to delete/archive the sandbox to clean up resources
#         # Note: Actual deletion may depend on the Daytona SDK's capabilities
#         logger.info(f"Attempting to clean up test sandbox {original_sandbox_id}")
#         # If there's a method to archive/delete the sandbox, call it here
#         # Example: daytona.archive_sandbox(sandbox.id)
#     except Exception as e:
#         logger.warning(f"Failed to clean up test sandbox {original_sandbox_id}: {str(e)}")

# if __name__ == "__main__":
#     import asyncio

#     # Configure any environment variables or setup needed for testing
#     load_dotenv()  # Ensure environment variables are loaded

#     # Run the test function
#     asyncio.run(test_agent())