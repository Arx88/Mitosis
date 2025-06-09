import React, { useEffect, useState } from 'react';
import { motion, useAnimation, AnimatePresence } from 'framer-motion';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { ToolViewProps } from '../types';
import { formatTimestamp, getToolTitle } from '../utils';
import { getToolIcon } from '../../utils';
import { CircleDashed, CheckCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

// Helper function to get a concise summary (basic implementation)
function getToolSummary(
  name: string,
  isSuccess: boolean,
  isStreaming: boolean,
  assistantContent?: string | null, // Not used in this basic version yet
  toolContent?: string | null       // Not used in this basic version yet
): string {
  if (isStreaming) {
    return "Processing...";
  }
  if (name === 'execute-command') {
    return isSuccess ? "Command executed" : "Execution failed";
  }
  if (name === 'web-search') {
    return isSuccess ? "Search complete" : "Search failed";
  }
  if (name === 'create-file') {
    return isSuccess ? "File created" : "File creation failed";
  }
  // Add more cases for other tools
  if (isSuccess) {
    return name === 'execute-command' ? 'Command output' :
           name === 'web-search' ? 'Search results' :
           name === 'create-file' ? 'File content' :
           'Output';
  }
  return name === 'execute-command' ? 'Command error' :
         name === 'web-search' ? 'Search error' :
         name === 'create-file' ? 'File error' :
         'Error output';
}

function getToolInputSummary(name: string, assistantContent?: string | null): string {
  if (!assistantContent) return "Input";

  try {
    // Check if assistantContent is JSON and contains specific fields for known tools
    const parsedContent = JSON.parse(assistantContent);
    if (name === 'execute-command' && parsedContent.command) {
      return `Command: ${parsedContent.command.substring(0, 50)}${parsedContent.command.length > 50 ? '...' : ''}`;
    }
    if (name === 'web-search' && parsedContent.query) {
      return `Search: ${parsedContent.query.substring(0, 50)}${parsedContent.query.length > 50 ? '...' : ''}`;
    }
    if (name === 'create-file' && parsedContent.file_path) {
      return `File: ${parsedContent.file_path}`;
    }
  } catch (e) {
    // Not JSON or doesn't match expected structure, fall through to generic summary
  }

  // Generic summary if specific parsing fails or tool is not recognized
  return name === 'execute-command' ? 'Command details' :
         name === 'web-search' ? 'Search parameters' :
         name === 'create-file' ? 'File details' :
         'Input';
}


export interface ToolViewWrapperProps extends ToolViewProps {
  children: React.ReactNode; // This will be the detailed output (toolContent)
  className?: string;
  showStatus?: boolean;
  customStatus?: {
    success?: string;
    failure?: string;
    streaming?: string;
  };
  // Removed contentClassName as children are now more structured
  // assistantContent is now handled directly for the input section
  };

const standardShadow = '0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)';
const toolWrapperAnimationVariants = {
  hidden: { opacity: 0, boxShadow: standardShadow }, // Removed y: 20
  visibleIdle: {
    opacity: 1, boxShadow: standardShadow, // Removed y: 0
    transition: { duration: 0.5, ease: "easeOut" } // Duration 0.5
  },
  visibleStreaming: {
    opacity: 1, // Removed y: 0
    boxShadow: [
      standardShadow + ", 0 0 0px 0px rgba(59, 130, 246, 0)",
      standardShadow + ", 0 0 15px 3px rgba(59, 130, 246, 0.5)",
      standardShadow + ", 0 0 0px 0px rgba(59, 130, 246, 0)"
    ],
    transition: {
      default: { duration: 0.5, ease: "easeOut" }, // Duration 0.5
      boxShadow: { duration: 1.5, repeat: Infinity, ease: "easeInOut", delay: 0.4 }
    }
  }
};

export function ToolViewWrapper({
  name = 'unknown',
  isSuccess = true,
  isStreaming = false,
  assistantTimestamp,
  toolTimestamp,
  children,
  className,
  showStatus = true, // Keep showStatus, it might control parts of the trigger
  customStatus, // Keep customStatus, might be used for summary
  assistantContent, // Pass through for getToolSummary
  toolContent,      // Pass through for getToolSummary
}: ToolViewWrapperProps) {
  const toolTitle = getToolTitle(name);
  const Icon = getToolIcon(name); // Main icon for the tool
  const MotionDiv = motion.div;
  const wrapperControls = useAnimation();

  // Determine unique values for accordion items based on available timestamps
  const inputAccordionValue = `input-${name}-${assistantTimestamp || 'no-assist-ts'}`;
  const outputAccordionValue = `output-${name}-${toolTimestamp || 'no-tool-ts'}`;

  // Default open state: open input if available, otherwise output. If streaming, prefer output.
  const getDefaultOpenValue = () => {
    if (isStreaming) return [outputAccordionValue];
    if (assistantContent) return [inputAccordionValue];
    if (children) return [outputAccordionValue]; // children is toolContent
    return [];
  };
  const [openAccordionItems, setOpenAccordionItems] = useState<string[]>(getDefaultOpenValue());

  const inputSummaryText = getToolInputSummary(name, assistantContent);
  const outputSummaryText = customStatus
    ? (isStreaming ? customStatus.streaming : (isSuccess ? customStatus.success : customStatus.failure)) || getToolSummary(name, isSuccess, isStreaming, assistantContent, toolContent)
    : getToolSummary(name, isSuccess, isStreaming, assistantContent, toolContent);


  useEffect(() => {
    if (isStreaming) {
      wrapperControls.start("visibleStreaming");
      // If streaming starts, ensure the output accordion is open
      if (!openAccordionItems.includes(outputAccordionValue)) {
        setOpenAccordionItems(prev => [...prev, outputAccordionValue]);
      }
    } else {
      wrapperControls.start("visibleIdle");
    }
  }, [isStreaming, wrapperControls, outputAccordionValue, openAccordionItems]);

  const iconAnimation = {
    initial: { opacity: 0, scale: 0.5 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.5 },
    transition: { duration: 0.3 }
  };

  const renderStatusIcon = (statusFor: 'input' | 'output') => {
    if (statusFor === 'input' && isStreaming && !assistantContent) return null; // No specific status for input if streaming output
    if (statusFor === 'input' && assistantContent) return <Icon className="h-4 w-4 text-muted-foreground" />; // Generic tool icon for input

    // Output status
    if (isStreaming) return <CircleDashed className="h-4 w-4 animate-spin text-blue-500" />;
    if (isSuccess) return <CheckCircle className="h-4 w-4 text-emerald-500" />;
    return <AlertTriangle className="h-4 w-4 text-red-500" />;
  };

  // NOTE on JSON/Code formatting:
  // The actual pretty-printing and syntax highlighting for JSON/code
  // should be handled by the component that renders `assistantContent` (for input)
  // or `children` (for output, which is toolContent).
  // This ToolViewWrapper provides the structure and basic styling.
  // For example, if `assistantContent` is a JSON string, the component rendering it
  // (likely part of `renderAssistantMessage` in `tool-call-side-panel.tsx`'s parent)
  // should parse it and use a syntax highlighter component.
  // This wrapper can apply a monospace font if it detects pre-formatted text.

  const contentBaseClass = "p-3 text-xs prose prose-sm dark:prose-invert max-w-none break-words overflow-x-auto scrollbar-thin scrollbar-thumb-zinc-300 dark:scrollbar-thumb-zinc-700 scrollbar-track-transparent";
  const inputContentBg = "bg-muted/20 dark:bg-muted/10";
  const outputContentBg = isSuccess ? "bg-background dark:bg-neutral-800/50" : "bg-destructive/5 dark:bg-destructive/10";


  return (
    <MotionDiv
      className={cn("w-full rounded-md overflow-hidden border border-border/80", className)}
      initial="hidden"
      animate={wrapperControls}
      variants={toolWrapperAnimationVariants}
    >
      <Accordion
        type="multiple" // Changed to multiple to allow both open if desired
        value={openAccordionItems}
        onValueChange={setOpenAccordionItems}
        className="w-full"
      >
        {assistantContent && (
          <AccordionItem value={inputAccordionValue} className="border-b border-border/80">
            <AccordionTrigger className="p-2 hover:no-underline focus:outline-none focus-visible:ring-1 focus-visible:ring-ring bg-muted/40 dark:bg-muted/20 rounded-t-md data-[state=open]:rounded-b-none">
              <div className="flex items-center w-full gap-2">
                {showStatus && renderStatusIcon('input')}
                <span className="text-xs font-semibold text-foreground truncate">
                  {toolTitle} - Input
                </span>
                {!openAccordionItems.includes(inputAccordionValue) && (
                  <span className="text-xs text-muted-foreground ml-1 truncate D_text-ellipsis">
                    : {inputSummaryText}
                  </span>
                )}
                {assistantTimestamp && (
                  <span className="text-xs text-muted-foreground ml-auto whitespace-nowrap">
                    {formatTimestamp(assistantTimestamp)}
                  </span>
                )}
              </div>
            </AccordionTrigger>
            <AccordionContent className={cn("max-h-60", inputContentBg, contentBaseClass)}>
              {/* Render assistantContent here. If it's a string, wrap in <pre> for monospace if it looks like code/JSON */}
              {typeof assistantContent === 'string' && (assistantContent.trim().startsWith('{') || assistantContent.trim().startsWith('[')) ? (
                <pre className="font-mono text-xs whitespace-pre-wrap">{JSON.stringify(JSON.parse(assistantContent), null, 2)}</pre>
              ) : (
                <div>{assistantContent}</div> // Or use a markdown renderer if it's markdown
              )}
            </AccordionContent>
          </AccordionItem>
        )}

        {/* Children (toolContent / Output) */}
        <AccordionItem value={outputAccordionValue} className={cn(!assistantContent ? "border-none" : "")}>
          <AccordionTrigger className={cn("p-2 hover:no-underline focus:outline-none focus-visible:ring-1 focus-visible:ring-ring", assistantContent ? "bg-background dark:bg-neutral-900/80" : "bg-muted/40 dark:bg-muted/20 rounded-t-md", {"rounded-b-none": openAccordionItems.includes(outputAccordionValue)})}>
            <div className="flex items-center w-full gap-2">
              {showStatus && renderStatusIcon('output')}
              <span className="text-xs font-semibold text-foreground truncate">
                {toolTitle} - {isSuccess ? "Output" : "Error"}
              </span>
              {!openAccordionItems.includes(outputAccordionValue) && (
                 <span className="text-xs text-muted-foreground ml-1 truncate D_text-ellipsis">
                    : {outputSummaryText}
                  </span>
              )}
              {toolTimestamp && (
                <span className="text-xs text-muted-foreground ml-auto whitespace-nowrap">
                  {formatTimestamp(toolTimestamp)}
                </span>
              )}
            </div>
          </AccordionTrigger>
          <AccordionContent className={cn("max-h-96", outputContentBg, contentBaseClass, !isSuccess && "border-t border-destructive/20")}>
             {/* Render children (toolContent) here. Apply similar logic for JSON/code as above if needed */}
            {typeof children === 'string' && (children.trim().startsWith('{') || children.trim().startsWith('[')) ? (
                <pre className="font-mono text-xs whitespace-pre-wrap">{children}</pre> // Basic pre for now
              ) : (
                <div>{children}</div> // Or use a markdown renderer
              )}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </MotionDiv>
  );
}
