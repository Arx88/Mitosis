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
  return isSuccess ? "Completed successfully" : "Failed";
}


export interface ToolViewWrapperProps extends ToolViewProps {
  children: React.ReactNode;
  // headerContent, footerContent, headerClassName, footerClassName are no longer used directly
  className?: string;
  contentClassName?: string; // Will be applied to the div inside AccordionContent
  showStatus?: boolean; // Still used for status icon in trigger
  customStatus?: { // Potentially use for custom summary text
    success?: string;
    failure?: string;
    streaming?: string;
  };
}

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
  contentClassName,
  showStatus = true, // Keep showStatus, it might control parts of the trigger
  customStatus, // Keep customStatus, might be used for summary
  assistantContent, // Pass through for getToolSummary
  toolContent,      // Pass through for getToolSummary
}: ToolViewWrapperProps) {
  const toolTitle = getToolTitle(name);
  const Icon = getToolIcon(name); // Main icon for the tool
  const MotionDiv = motion.div;
  const wrapperControls = useAnimation();
  const [isAccordionOpen, setIsAccordionOpen] = useState(false);

  const summaryText = customStatus
    ? (isStreaming ? customStatus.streaming : (isSuccess ? customStatus.success : customStatus.failure)) || getToolSummary(name, isSuccess, isStreaming, assistantContent, toolContent)
    : getToolSummary(name, isSuccess, isStreaming, assistantContent, toolContent);

  const uniqueAccordionValue = `${name}-${assistantTimestamp || ''}-${toolTimestamp || ''}`;

  useEffect(() => {
    if (isStreaming) {
      wrapperControls.start("visibleStreaming");
    } else {
      wrapperControls.start("visibleIdle");
    }
  }, [isStreaming, wrapperControls]);

  const iconAnimation = {
    initial: { opacity: 0, scale: 0.5 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.5 },
    transition: { duration: 0.3 } // Duration 0.3
  };

  return (
    <MotionDiv
      className={cn("w-full rounded-md overflow-hidden", className)} // main className here, shadow controlled by variants
      initial="hidden"
      animate={wrapperControls}
      variants={toolWrapperAnimationVariants}
    >
      <Accordion
        type="single"
        collapsible
        className="w-full"
        onValueChange={(value) => setIsAccordionOpen(!!value)}
      >
        <AccordionItem value={uniqueAccordionValue} className="border-none">
          <AccordionTrigger className="p-2 hover:no-underline focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-t-md bg-gradient-to-r from-zinc-100 to-zinc-200 dark:from-zinc-800 dark:to-zinc-900 data-[state=open]:rounded-b-none data-[state=open]:border-b data-[state=open]:border-border">
            <div className="flex items-center w-full gap-2">
              {showStatus && (
                <AnimatePresence mode="wait">
                  {isStreaming ? (
                    <MotionDiv key="streaming" {...iconAnimation}>
                      <CircleDashed className="h-4 w-4 animate-spin text-blue-500" />
                    </MotionDiv>
                  ) : isSuccess ? (
                    <MotionDiv key="success" {...iconAnimation}>
                      <CheckCircle className="h-4 w-4 text-emerald-500" />
                    </MotionDiv>
                  ) : (
                    <MotionDiv key="failure" {...iconAnimation}>
                      <AlertTriangle className="h-4 w-4 text-red-500" />
                    </MotionDiv>
                  )}
                </AnimatePresence>
              )}

              {Icon && !isStreaming && ( // Show tool icon only when not streaming for space
                <MotionDiv
                  initial={{opacity:0, scale: 0.8}} animate={{opacity:1, scale:1}} transition={{delay: 0.1}}
                  className="flex items-center justify-center bg-slate-200 dark:bg-slate-700 p-0.5 rounded-sm"
                >
                  <Icon className="h-3.5 w-3.5 text-slate-600 dark:text-slate-300" />
                </MotionDiv>
              )}

              <MotionDiv className="flex-1 text-left">
                <span className="text-sm font-medium text-foreground truncate">
                  {toolTitle}
                </span>
                {!isAccordionOpen && summaryText && ( // Show summary only when collapsed
                  <span className="text-sm text-muted-foreground ml-1 truncate">
                    - {summaryText}
                  </span>
                )}
              </MotionDiv>

              {!isStreaming && (toolTimestamp || assistantTimestamp) && (
                <span className="text-xs text-muted-foreground ml-auto whitespace-nowrap">
                  {formatTimestamp(toolTimestamp || assistantTimestamp || '')}
                </span>
              )}
            </div>
            {/* The default chevron will appear here, controlled by AccordionTrigger */}
          </AccordionTrigger>
          <AccordionContent className="p-0 border-t border-border">
            <div className={cn("overflow-auto bg-gradient-to-r from-zinc-50 to-zinc-100 dark:from-zinc-800 dark:to-zinc-900", contentClassName)}>
              {children}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </MotionDiv>
  );
}
