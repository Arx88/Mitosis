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
    <div className="border-l-4 border-blue-500 pl-4 py-2 my-4 bg-blue-50 dark:bg-gray-800">
      <h3 className="font-semibold text-lg mb-2 text-blue-800 dark:text-blue-300">Plan de Acción</h3>
      <Markdown content={content} />
    </div>
  );
};
