import React, { useEffect } from 'react';
import { motion, useAnimation } from 'framer-motion';
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

const standardShadow = '0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)'; // Tailwind's shadow-lg, -4px for the second part as per shadow-lg
// For blue-500 glow: rgba(59, 130, 246, ...)

const toolWrapperAnimationVariants = {
  hidden: { opacity: 0, y: 20, boxShadow: standardShadow },
  visibleIdle: {
    opacity: 1,
    y: 0,
    boxShadow: standardShadow,
    transition: { duration: 0.4, ease: "easeOut" }
  },
  visibleStreaming: {
    opacity: 1,
    y: 0,
    boxShadow: [
      standardShadow + ", 0 0 0px 0px rgba(59, 130, 246, 0)",
      standardShadow + ", 0 0 15px 3px rgba(59, 130, 246, 0.5)",
      standardShadow + ", 0 0 0px 0px rgba(59, 130, 246, 0)"
    ],
    transition: {
      // Default transition for opacity and y (if they were to change with variants, though they don't here beyond initial)
      default: { duration: 0.4, ease: "easeOut" },
      // Specific transition for boxShadow
      boxShadow: { duration: 1.5, repeat: Infinity, ease: "easeInOut", delay: 0.4 } // Delay ensures entry animation completes
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
  const flashOverlayControls = useAnimation();
  const wrapperControls = useAnimation(); // New controls for the wrapper

  useEffect(() => {
    if (!isStreaming && showStatus) {
      const flashColor = isSuccess
        ? 'rgba(52, 211, 153, 1)'
        : 'rgba(239, 68, 68, 1)';

      flashOverlayControls.start({
        opacity: [0, 0.3, 0],
        backgroundColor: [flashColor, flashColor, flashColor],
        transition: { duration: 0.7, times: [0, 0.15, 1] }
      });
    }
  }, [isSuccess, isStreaming, showStatus, flashOverlayControls]);

  useEffect(() => {
    // This effect handles both initial animation from "hidden" and subsequent changes
    if (isStreaming) {
      wrapperControls.start("visibleStreaming");
    } else {
      wrapperControls.start("visibleIdle");
    }
  }, [isStreaming, wrapperControls]);

  return (
    <MotionDiv
      className={cn("flex flex-col h-full rounded-md", className)} // Removed shadow-lg
      initial="hidden"
      animate={wrapperControls}
      variants={toolWrapperAnimationVariants}
    >
      {(headerContent || showStatus) && (
        <div className={cn(
          "relative flex items-center p-2 bg-gradient-to-r from-sky-100 to-sky-200 dark:from-sky-700 dark:to-sky-900 justify-between border-zinc-200 dark:border-zinc-800",
          headerClassName
        )}>
          <MotionDiv
            className="absolute inset-0 pointer-events-none"
            style={{ zIndex: 0 }}
            animate={flashOverlayControls}
          />
          <div className="flex ml-1 items-center" style={{ zIndex: 1 }}>
            {Icon && (
              <MotionDiv
                whileHover={{ scale: 1.2, rotate: 5 }}
                transition={{ type: 'spring', stiffness: 300 }}
              >
                <Icon className="h-4 w-4 mr-2 text-zinc-600 dark:text-zinc-400" />
              </MotionDiv>
            )}
            <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              {toolTitle}
            </span>
          </div>
          <div style={{ zIndex: 1 }}>
            {headerContent}
          </div>
        </div>
      )}

      <div className={cn("flex-1 overflow-auto", contentClassName)}>
        {children}
      </div>

      {(footerContent || showStatus) && (
        <div className={cn(
          "p-4 border-t border-zinc-200 dark:border-zinc-800 bg-gradient-to-r from-neutral-100 to-neutral-200 dark:from-neutral-700 dark:to-neutral-900",
          footerClassName
        )}>
          <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
            {!isStreaming && showStatus && (
              <div className="flex items-center gap-2">
                {isSuccess ? (
                  <motion.div // Can also be MotionDiv if preferred, but direct motion.div is fine here
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
                <MotionDiv
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1, duration: 0.3 }}
                >
                  <span className="text-sm">
                    {isSuccess
                      ? customStatus?.success || "Completed successfully"
                      : customStatus?.failure || "Execution failed"}
                  </span>
                </MotionDiv>
              </div>
            )}

            {isStreaming && showStatus && (
              <div className="flex items-center gap-2">
                <CircleDashed className="h-3.5 w-3.5 text-blue-500 animate-spin" />
                <span className="text-sm">{customStatus?.streaming || "Processing..."}</span>
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
