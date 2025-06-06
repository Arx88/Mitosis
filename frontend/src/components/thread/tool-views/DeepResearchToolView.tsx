import React from 'react';
import { ToolViewProps } from './types';

export const DeepResearchToolView: React.FC<ToolViewProps> = ({
  name,
  agentStatus,
  isSuccess,
  assistantContent,
  toolContent,
}) => {
  return (
    <div>
      <h3>Deep Research Tool</h3>
      <p>Tool Name/ID: {name || 'N/A'}</p>
      <p>Status: {agentStatus || (isSuccess ? 'Completed' : 'Unknown')}</p>
      {assistantContent && <p>Assistant Content: {assistantContent}</p>}
      {toolContent && <p>Tool Content: {toolContent}</p>}
      {/* Add more detailed view based on available props */}
    </div>
  );
};

export default DeepResearchToolView;
