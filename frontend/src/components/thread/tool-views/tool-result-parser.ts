/**
 * Tool Result Parser for handling both old and new tool result formats
 * 
 * Supports:
 * - New structured format with tool_execution
 * - Legacy XML-wrapped format
 * - Legacy direct format
 */

export interface ParsedToolResult {
  toolName: string;
  functionName: string;
  xmlTagName?: string;
  toolOutput: string;
  isSuccess: boolean;
  arguments?: Record<string, any>;
  timestamp?: string;
  toolCallId?: string;
  summary?: string;
}

/**
 * Parse tool result content from various formats
 */
export function parseToolResult(content: any): ParsedToolResult | null {
  try {
    // Handle string content
    if (typeof content === 'string') {
      return parseStringToolResult(content);
    }

    // Handle object content
    if (typeof content === 'object' && content !== null) {
      return parseObjectToolResult(content);
    }

    return null;
  } catch (error) {
    console.error('Error parsing tool result:', error);
    return null;
  }
}

/**
 * Parse string-based tool result (legacy format)
 */
function parseStringToolResult(content: string): ParsedToolResult | null {
  // Try to parse as JSON first
  try {
    const parsed = JSON.parse(content);
    if (typeof parsed === 'object') {
      return parseObjectToolResult(parsed);
    }
  } catch {
    // Not JSON, continue with string parsing
  }

  // Extract tool name from XML tags
  const toolMatch = content.match(/<\/?([\w-]+)>/);
  const toolName = toolMatch ? toolMatch[1] : 'unknown';

  // Check for success in ToolResult format
  let isSuccess = true;
  if (content.includes('ToolResult')) {
    const successMatch = content.match(/success\s*=\s*(True|False|true|false)/i);
    if (successMatch) {
      isSuccess = successMatch[1].toLowerCase() === 'true';
    }
  }

  return {
    toolName: toolName.replace(/_/g, '-'),
    functionName: toolName.replace(/-/g, '_'),
    toolOutput: content,
    isSuccess,
  };
}

/**
 * Parse object-based tool result (new and legacy formats)
 */
function parseObjectToolResult(content: any): ParsedToolResult | null {
  // New structured format with tool_execution
  if ('tool_execution' in content && typeof content.tool_execution === 'object') {
    const toolExecution = content.tool_execution;
    const functionName = toolExecution.function_name || 'unknown';
    const xmlTagName = toolExecution.xml_tag_name || '';
    const toolName = (xmlTagName || functionName).replace(/_/g, '-');

    let determinedOutput = '';
    const resultObj = toolExecution.result;
    if (resultObj) {
        if (typeof resultObj.output === 'string' && resultObj.output.trim() !== '') {
            determinedOutput = resultObj.output;
        } else if (typeof resultObj === 'string' && resultObj.trim() !== '') {
            determinedOutput = resultObj;
        }
    }

    return {
      toolName,
      functionName,
      xmlTagName: xmlTagName || undefined,
      toolOutput: determinedOutput,
      isSuccess: toolExecution.result?.success !== false,
      arguments: toolExecution.arguments,
      timestamp: toolExecution.execution_details?.timestamp,
      toolCallId: toolExecution.tool_call_id,
      summary: content.summary,
    };
  }

  // Handle nested format with role and content
  if ('role' in content && 'content' in content && typeof content.content === 'object') {
    const nestedContent = content.content;
    
    // Check for new structured format nested in content
    if ('tool_execution' in nestedContent && typeof nestedContent.tool_execution === 'object') {
      return parseObjectToolResult(nestedContent);
    }

    // Legacy format with tool_name/xml_tag_name
    if ('tool_name' in nestedContent || 'xml_tag_name' in nestedContent) {
      const toolName = (nestedContent.tool_name || nestedContent.xml_tag_name || 'unknown').replace(/_/g, '-');

      let nestedDeterminedOutput = '';
      if (nestedContent.result) {
          if (typeof nestedContent.result.output === 'string' && nestedContent.result.output.trim() !== '') {
              nestedDeterminedOutput = nestedContent.result.output;
          } else if (typeof nestedContent.result === 'string' && nestedContent.result.trim() !== '') {
              nestedDeterminedOutput = nestedContent.result;
          }
      } else if (typeof nestedContent.output === 'string' && nestedContent.output.trim() !== '') {
          nestedDeterminedOutput = nestedContent.output;
      }

      return {
        toolName,
        functionName: toolName.replace(/-/g, '_'),
        toolOutput: nestedDeterminedOutput,
        isSuccess: nestedContent.result?.success !== false, // isSuccess logic might also need refinement if result object structure varies
      };
    }
  }

  // Handle nested format with role and string content
  if ('role' in content && 'content' in content && typeof content.content === 'string') {
    // This path typically means the content itself is the output, or needs further parsing as a string
    const stringResult = parseStringToolResult(content.content);
    if (stringResult) return stringResult; // Return as is, parseStringToolResult handles its own output format
  }

  // Legacy direct format
  if ('tool_name' in content || 'xml_tag_name' in content) {
    const toolName = (content.tool_name || content.xml_tag_name || 'unknown').replace(/_/g, '-');

    let legacyDeterminedOutput = '';
    if (content.result) {
        if (typeof content.result.output === 'string' && content.result.output.trim() !== '') {
            legacyDeterminedOutput = content.result.output;
        } else if (typeof content.result === 'string' && content.result.trim() !== '') {
            legacyDeterminedOutput = content.result;
        }
    } else if (typeof content.output === 'string' && content.output.trim() !== '') {
        legacyDeterminedOutput = content.output;
    }

    return {
      toolName,
      functionName: toolName.replace(/-/g, '_'),
      toolOutput: legacyDeterminedOutput,
      isSuccess: content.result?.success !== false, // isSuccess logic might also need refinement
    };
  }

  // If content is a simple string and not parsed by other means, treat it as output
  if (typeof content === 'string') {
    return {
      toolName: 'unknown',
      functionName: 'unknown',
      toolOutput: content,
      isSuccess: true, // Assume success if it's just a string output
    };
  }

  // Fallback for unhandled object structures that might represent an error or simple output
  if (typeof content === 'object' && content !== null) {
    if (typeof content.output === 'string') {
      return {
        toolName: content.toolName || content.name || 'unknown',
        functionName: (content.toolName || content.name || 'unknown').replace(/-/g, '_'),
        toolOutput: content.output,
        isSuccess: content.isSuccess !== false,
        summary: content.summary,
      };
    }
    // If it's an object but doesn't match known structures, try to stringify it as a last resort for output
    // This helps in cases where the result is a simple JSON object not fitting other patterns.
    try {
      const stringifiedOutput = JSON.stringify(content);
      return {
        toolName: 'unknown_object',
        functionName: 'unknown_object',
        toolOutput: stringifiedOutput,
        isSuccess: true, // Assume success
      };
    } catch (e) {
      // ignore stringify error
    }
  }

  return null;
}

/**
 * Check if content contains a tool result
 */
export function isToolResult(content: any): boolean {
  if (typeof content === 'string') {
    return content.includes('<tool_result>') || content.includes('ToolResult');
  }

  if (typeof content === 'object' && content !== null) {
    return (
      'tool_execution' in content ||
      ('role' in content && 'content' in content) ||
      'tool_name' in content ||
      'xml_tag_name' in content
    );
  }

  return false;
}

/**
 * Format tool name for display (convert kebab-case to Title Case)
 */
export function formatToolNameForDisplay(toolName: string): string {
  return toolName
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
} 