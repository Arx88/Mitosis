import React from 'react';
import { ToolViewProps } from './types';

export const DeepResearchToolView: React.FC<ToolViewProps> = ({ toolCall }) => {
  return (
    <div>
      <h3>Deep Research Tool</h3>
      <p>Tool call ID: {toolCall.id}</p>
      <p>Status: {toolCall.status}</p>
      {/* Add more detailed view based on toolCall.input and toolCall.output */}
    </div>
  );
};

export default DeepResearchToolView;
