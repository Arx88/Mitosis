import React from 'react';
import { Markdown } from '@/components/ui/markdown'; // Reutilizamos el componente de Markdown
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from '../ui/collapsible';

interface ReasoningViewProps {
  content: string;
}

export const ReasoningView: React.FC<ReasoningViewProps> = ({ content }) => {
  if (!content) {
    return null;
  }

  return (
    <Collapsible>
      <div className="bg-slate-100 dark:bg-slate-800 p-4 rounded-lg">
        <CollapsibleTrigger>Pensamiento del Agente</CollapsibleTrigger>
        <CollapsibleContent>
          <Markdown>{content}</Markdown>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
};
