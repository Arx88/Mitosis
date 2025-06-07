import React from 'react';
import { motion } from 'framer-motion';
import { ToolViewProps } from '../types';
import { formatTimestamp, getToolTitle } from '../utils';
import { getToolIcon } from '../../utils';
import { CircleDashed, CheckCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ToolViewWrapperProps extends ToolViewProps {
  children: React.ReactNode;
  headerContent?: React.ReactNode;
  footerContent?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  headerClassName?: string;
  footerClassName?: string;
  showStatus?: boolean;
  customStatus?: {
    success?: string;
    failure?: string;
    streaming?: string;
  };
}

export function ToolViewWrapper({
  name = 'unknown',
  isSuccess = true,
  isStreaming = false,
  assistantTimestamp,
  toolTimestamp,
  children,
  headerContent,
  footerContent,
  className,
  contentClassName,
  headerClassName,
  footerClassName,
  showStatus = true,
  customStatus,
}: ToolViewWrapperProps) {
  const toolTitle = getToolTitle(name);
  const Icon = getToolIcon(name);
  const MotionDiv = motion.div;

  return (
    <MotionDiv
      className={cn("flex flex-col h-full", className)}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {(headerContent || showStatus) && (
        <div className={cn(
          "flex items-center p-2 bg-gradient-to-r from-zinc-100 to-zinc-200 dark:from-zinc-800 dark:to-zinc-900 justify-between border-zinc-200 dark:border-zinc-800",
          headerClassName
        )}>
          <div className="flex ml-1 items-center">
            {Icon && <Icon className="h-4 w-4 mr-2 text-zinc-600 dark:text-zinc-400" />}
            <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
              {toolTitle}
            </span>
          </div>
          {headerContent}
        </div>
      )}

      <div className={cn("flex-1 overflow-auto", contentClassName)}>
        {children}
      </div>

      {(footerContent || showStatus) && (
        <div className={cn(
          "p-4 border-t border-zinc-200 dark:border-zinc-800 bg-gradient-to-r from-zinc-50 to-zinc-100 dark:from-zinc-800 dark:to-zinc-900",
          footerClassName
        )}>
          <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
            {!isStreaming && showStatus && (
              <div className="flex items-center gap-2">
                {isSuccess ? (
                  <motion.div
                    initial={{ scale: 0.5, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                  </motion.div>
                ) : (
                  <motion.div
                    initial={{ scale: 0.5, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                  </motion.div>
                )}
                <span>
                  {isSuccess
                    ? customStatus?.success || "Completed successfully"
                    : customStatus?.failure || "Execution failed"}
                </span>
              </div>
            )}

            {isStreaming && showStatus && (
              <div className="flex items-center gap-2">
                <CircleDashed className="h-3.5 w-3.5 text-blue-500 animate-spin" />
                <span>{customStatus?.streaming || "Processing..."}</span>
              </div>
            )}

            <div className="text-xs">
              {toolTimestamp && !isStreaming
                ? formatTimestamp(toolTimestamp)
                : assistantTimestamp
                  ? formatTimestamp(assistantTimestamp)
                  : ""}
            </div>

            {footerContent}
          </div>
        </div>
      )}
    </MotionDiv>
  );
} 
