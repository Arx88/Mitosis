import React, { useState, useEffect } from 'react';
import { useThinkingTimer } from '@/hooks/useThinkingTimer';

interface ReasoningViewProps {
  // The actual reasoning content (text or markdown) to display.
  // Can be null or undefined if no content is available yet.
  content: string | null; // Changed from string | null | undefined to string | null as per instruction context
  // Optional flag to indicate if the agent is actively streaming or processing.
  // Used to show a "Thinking..." placeholder if `content` is empty but the agent is active.
  isStreamingAgentActive?: boolean;
}

export const ReasoningView: React.FC<ReasoningViewProps> = ({ content, isStreamingAgentActive }) => {
  console.log(`[TIMER_DEBUG] ReasoningView - Received props.isStreamingAgentActive:`, isStreamingAgentActive);
  const formattedTime = useThinkingTimer(isStreamingAgentActive || false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [displayedThoughts, setDisplayedThoughts] = useState<string[]>([]);

  // console.log(`[REASONING_DEBUG] ReasoningView - Props:`, { content, isStreamingAgentActive });
  useEffect(() => {
    console.log(`[REASONING_DEBUG] ReasoningView - Received content prop:`, content); // Add this log
    if (content && content.trim() !== '') {
      const thoughts = content.split('\n');
      setDisplayedThoughts(thoughts);
      console.log(`[REASONING_DEBUG] ReasoningView - Set displayedThoughts:`, thoughts); // Add this log
    } else {
      setDisplayedThoughts([]);
      console.log(`[REASONING_DEBUG] ReasoningView - Cleared displayedThoughts`); // Add this log
    }
  }, [content]);

  // If the agent is not active and there's no persistent content, don't render the component.
  // This check is slightly different from the new JSX's internal content area check,
  // ensuring the entire component (including header) doesn't show if there's nothing to show at all.
  if (!isStreamingAgentActive && (!content || content.trim() === '')) {
    return null;
  }

  const contentAreaStyle = {
    overflow: 'hidden',
    maxHeight: isExpanded ? 'none' : '5em',
    transition: 'max-height 0.3s ease-in-out',
    minHeight: (displayedThoughts.length === 0 && isStreamingAgentActive) ? '4em' : 'auto'
  };

  return (
    <div className="reasoning-view-container bg-slate-100 dark:bg-slate-800 p-4 rounded-lg text-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center">
          <span className="mr-2 thinking-icon">⚙️</span> {/* Existing animated icon */}
          <span className="font-semibold">Agent Thoughts</span>
          {isStreamingAgentActive && (
            <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
              (Thinking for {formattedTime})
            </span>
          )}
        </div>
        {/* Only show expand toggle if there are thoughts to expand/collapse */}
        {displayedThoughts.length > 0 && (
           <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline focus:outline-none"
          >
            {isExpanded ? 'Collapse' : 'Expand for detail'}
          </button>
        )}
      </div>

      {/* Content Area for Thoughts */}
      {/* Render this section if agent is active OR if there's persistent content */}
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
            isStreamingAgentActive && ( /* Only show "Thinking..." if agent is active and no thoughts yet */
              <div className="text-gray-500 dark:text-gray-400 italic">Thinking...</div>
            )
          )}
        </div>
      )}
    </div>
  );
};
