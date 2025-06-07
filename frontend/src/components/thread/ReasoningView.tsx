import React from 'react';
import { Markdown } from '@/components/ui/markdown'; // Reutilizamos el componente de Markdown

interface ReasoningViewProps {
  content: string;
}

export const ReasoningView: React.FC<ReasoningViewProps> = ({ content }) => {
  if (!content) {
    return null;
  }

  return (
    <div className="reasoning-view-container bg-slate-100 dark:bg-slate-800 p-4 rounded-lg">
      <div className="flex items-center mb-2">
        <span className="mr-2 thinking-icon">⚙️</span>
        <span className="font-semibold">Pensamiento del Agente</span>
      </div>
      <Markdown>{content}</Markdown>
    </div>
  );
};
