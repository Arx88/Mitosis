import React, { useState, useEffect } from 'react';
import { motion, useAnimation } from 'framer-motion'; // Added useAnimation
import { ChevronDown } from 'lucide-react';
import { useThinkingTimer } from '@/hooks/useThinkingTimer';

interface ReasoningViewProps {
  content: string | null;
  isStreamingAgentActive?: boolean;
}

const standardShadow = '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)'; // Tailwind's shadow-md

const animationVariants = {
  hidden: { opacity: 0, y: 20, boxShadow: standardShadow },
  visibleInactive: {
    opacity: 1,
    y: 0,
    boxShadow: standardShadow,
    transition: { duration: 0.4, ease: "easeOut" }
  },
  visibleActive: {
    opacity: 1,
    y: 0,
    boxShadow: [
      standardShadow + ", 0 0 0px 0px rgba(59, 130, 246, 0)",    // blue-500 with 0 opacity
      standardShadow + ", 0 0 15px 3px rgba(59, 130, 246, 0.6)", // blue-500 with 0.6 opacity
      standardShadow + ", 0 0 0px 0px rgba(59, 130, 246, 0)"     // blue-500 with 0 opacity
    ],
    transition: {
      default: { duration: 0.4, ease: "easeOut" }, // For opacity/y if they change
      boxShadow: { duration: 1.5, repeat: Infinity, ease: "easeInOut", delay: 0.4 }
    }
  }
};

export const ReasoningView: React.FC<ReasoningViewProps> = ({ content, isStreamingAgentActive }) => {
  const MotionDiv = motion.div;
  const MotionButton = motion.button;
  const controls = useAnimation(); // Added

  console.log(`[TIMER_DEBUG] ReasoningView - Received props.isStreamingAgentActive:`, isStreamingAgentActive);
  const formattedTime = useThinkingTimer(isStreamingAgentActive || false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [displayedThoughts, setDisplayedThoughts] = useState<string[]>([]);

  useEffect(() => {
    console.log(`[REASONING_DEBUG] ReasoningView - Received content prop:`, content);
    const htmlParagraphRegex = /^<p>.*<\/p>$/i;
    const placeholderRegex = /reasoning-view-\d+/i;

    // Ensure content is treated as a string for .trim() and .split()
    const currentContentStr = content || "";

    if (currentContentStr.trim() !== '' && !htmlParagraphRegex.test(currentContentStr.trim()) && !placeholderRegex.test(currentContentStr.trim())) {
      const thoughts = currentContentStr.split('\n');
      setDisplayedThoughts(thoughts);
      console.log(`[REASONING_DEBUG] ReasoningView - Set displayedThoughts:`, thoughts);
    } else {
      if (currentContentStr && (htmlParagraphRegex.test(currentContentStr.trim()) || placeholderRegex.test(currentContentStr.trim()))) {
        console.warn(`[REASONING_DEBUG] ReasoningView - Invalid content detected, treating as empty:`, currentContentStr);
      }
      setDisplayedThoughts([]);
      console.log(`[REASONING_DEBUG] ReasoningView - Cleared displayedThoughts (or content was invalid/empty)`);
    }
  }, [content]);

  useEffect(() => {
    if (isStreamingAgentActive) {
      controls.start("visibleActive");
    } else {
      // On initial load if not streaming, or when streaming stops
      controls.start("visibleInactive");
    }
  }, [isStreamingAgentActive, controls]);


  if (!isStreamingAgentActive && (!content || content.trim() === '')) {
    // If not actively thinking AND there's no persistent content, don't render.
    // This ensures that if content clears after streaming, the component disappears
    // rather than just going to inactive (unless it has persistent content).
    // The 'hidden' initial state of variants handles the very first appearance.
    return null;
  }

  const contentAreaStyle = {
    overflow: 'hidden',
    maxHeight: isExpanded ? 'none' : '5em',
    transition: 'max-height 0.3s ease-in-out',
    minHeight: (displayedThoughts.length === 0 && isStreamingAgentActive) ? '4em' : 'auto'
  };

  return (
    <MotionDiv
      className="reasoning-view-container bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700 dark:to-slate-800 p-4 rounded-lg text-sm" // Removed shadow-md
      initial="hidden"
      animate={controls}
      variants={animationVariants}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center">
          <span className="mr-2 thinking-icon">⚙️</span>
          <span className="font-semibold">Agent Thoughts</span>
          {isStreamingAgentActive && (
            <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
              (Thinking for {formattedTime})
            </span>
          )}
        </div>
        {displayedThoughts.length > 0 && (
           <MotionButton
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 focus:outline-none" // Changed text-xs to text-sm
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {isExpanded ? 'Collapse' : 'Expand for detail'}
            <ChevronDown
              className="h-3 w-3 transition-transform duration-200"
              style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
            />
          </MotionButton>
        )}
      </div>

      {(isStreamingAgentActive || (content && content.trim() !== '')) && (
        <div
          className="thoughts-content-area mt-2 border-t pt-2 border-slate-200 dark:border-slate-700"
          style={contentAreaStyle}
        >
          {displayedThoughts.length > 0 ? (
            <div className="thoughts-list-container">
              {displayedThoughts.map((thought, index) => (
                <div key={index} className="text-gray-700 dark:text-gray-300 py-0.5 whitespace-pre-wrap thought-item">
                  {thought}
                </div>
              ))}
            </div>
          ) : (
            isStreamingAgentActive && (
              <div className="flex items-center justify-center py-2">
                <div className="flex space-x-1">
                  {[0, 1, 2].map((i) => (
                    <MotionDiv
                      key={i}
                      className="h-1.5 w-1.5 bg-slate-500 dark:bg-slate-400 rounded-full"
                      initial={{ opacity: 0.5 }}
                      animate={{ opacity: [0.5, 1, 0.5], y: [0, -2, 0] }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        delay: i * 0.2,
                      }}
                    />
                  ))}
                </div>
              </div>
            )
          )}
        </div>
      )}
    </MotionDiv>
  );
};
