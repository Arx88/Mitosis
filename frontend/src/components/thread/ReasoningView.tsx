import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion'; // Added
import { ChevronDown } from 'lucide-react'; // Added
import { useThinkingTimer } from '@/hooks/useThinkingTimer';

interface ReasoningViewProps {
  content: string | null;
  isStreamingAgentActive?: boolean;
}

export const ReasoningView: React.FC<ReasoningViewProps> = ({ content, isStreamingAgentActive }) => {
  const MotionDiv = motion.div; // Added
  const MotionButton = motion.button; // Added

  console.log(`[TIMER_DEBUG] ReasoningView - Received props.isStreamingAgentActive:`, isStreamingAgentActive);
  const formattedTime = useThinkingTimer(isStreamingAgentActive || false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [displayedThoughts, setDisplayedThoughts] = useState<string[]>([]);

  useEffect(() => {
    console.log(`[REASONING_DEBUG] ReasoningView - Received content prop:`, content);
    if (content && content.trim() !== '') {
      const thoughts = content.split('\n');
      setDisplayedThoughts(thoughts);
      console.log(`[REASONING_DEBUG] ReasoningView - Set displayedThoughts:`, thoughts);
    } else {
      setDisplayedThoughts([]);
      console.log(`[REASONING_DEBUG] ReasoningView - Cleared displayedThoughts`);
    }
  }, [content]);

  if (!isStreamingAgentActive && (!content || content.trim() === '')) {
    return null;
  }

  const contentAreaStyle = {
    overflow: 'hidden',
    maxHeight: isExpanded ? 'none' : '5em', // Keep existing max-height logic for collapse
    transition: 'max-height 0.3s ease-in-out', // Keep existing transition
    minHeight: (displayedThoughts.length === 0 && isStreamingAgentActive) ? '4em' : 'auto'
  };

  return (
    <MotionDiv
      className="reasoning-view-container bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700 dark:to-slate-800 p-4 rounded-lg text-sm shadow-md" // Added shadow, changed bg
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center">
          <span className="mr-2 thinking-icon">⚙️</span>
          <span className="font-semibold">Agent Thoughts</span>
          {isStreamingAgentActive && (
            <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
              (Thinking for {formattedTime})
            </span>
          )}
        </div>
        {displayedThoughts.length > 0 && (
           <MotionButton // Changed to MotionButton
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 focus:outline-none" // Added flex, gap; updated hover
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
          style={contentAreaStyle} // Keep using style for max-height animation
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
            isStreamingAgentActive && ( // Only show "Thinking..." if agent is active and no thoughts yet
              <div className="flex items-center justify-center py-2"> {/* Centering container */}
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
