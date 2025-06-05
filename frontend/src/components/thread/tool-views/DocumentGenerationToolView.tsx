'use client';

import React from 'react';
import {
  CheckCircle,
  AlertTriangle,
  FileText,
  DownloadCloud,
  Wrench,
} from 'lucide-react';
import { ToolViewProps } from './types';
import { formatTimestamp, getToolTitle, extractToolData } from './utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from "@/components/ui/scroll-area";
import { LoadingState } from './shared/LoadingState';
import { FileRenderer } from '@/components/file-renderers'; // For potential future use or direct link rendering

interface DocumentGenerationOutput {
  document_path?: string;
  message?: string;
  // Other fields like title, author might be present if we enhance the tool's output
}

export function DocumentGenerationToolView({
  name = 'document-generation', // Default, can be overridden by actual tool name
  assistantContent,
  toolContent,
  assistantTimestamp,
  toolTimestamp,
  isSuccess = true,
  isStreaming = false,
  project, // Pass project for potential sandbox URLs if needed for FileRenderer
}: ToolViewProps) {
  const toolTitle = getToolTitle(name);

  const parsedToolOutput = React.useMemo(() => {
    if (!toolContent) return null;
    const { toolResult } = extractToolData(toolContent);
    if (toolResult?.toolOutput) {
      if (typeof toolResult.toolOutput === 'string') {
        try {
          return JSON.parse(toolResult.toolOutput) as DocumentGenerationOutput;
        } catch (e) {
          console.error("Error parsing toolOutput JSON:", e);
          return { message: "Error parsing output." } as DocumentGenerationOutput;
        }
      } else if (typeof toolResult.toolOutput === 'object') {
        return toolResult.toolOutput as DocumentGenerationOutput;
      }
    }
    return null;
  }, [toolContent]);

  const documentPath = parsedToolOutput?.document_path;
  const displayMessage = parsedToolOutput?.message || (isSuccess ? "Document generated." : "Failed to generate document.");
  const fileName = documentPath ? documentPath.split('/').pop() : 'generated_document';

  // In a real scenario, this would be a direct link to download from the backend/sandbox
  // For now, if it's a sandbox path, we can't directly link.
  // If the document_path is a full URL, it could be used directly.
  // Assuming document_path is currently a host path or sandbox path not directly accessible.
  // We'll render it as text and show a "download" concept.
  // A real implementation would need backend support to serve these files.

  const canDirectlyLink = documentPath && (documentPath.startsWith('http://') || documentPath.startsWith('https://'));

  return (
    <Card className="gap-0 flex border shadow-none border-t border-b-0 border-x-0 p-0 rounded-none flex-col h-full overflow-hidden bg-white dark:bg-zinc-950">
      <CardHeader className="h-14 bg-zinc-50/80 dark:bg-zinc-900/80 backdrop-blur-sm border-b p-2 px-4 space-y-2">
        <div className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="relative p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-purple-600/10 border border-purple-500/20">
              <FileText className="w-5 h-5 text-purple-500 dark:text-purple-400" />
            </div>
            <div>
              <CardTitle className="text-base font-medium text-zinc-900 dark:text-zinc-100">
                {toolTitle}
              </CardTitle>
            </div>
          </div>

          {!isStreaming && (
            <Badge
              variant="secondary"
              className={
                isSuccess
                  ? "bg-gradient-to-b from-emerald-200 to-emerald-100 text-emerald-700 dark:from-emerald-800/50 dark:to-emerald-900/60 dark:text-emerald-300"
                  : "bg-gradient-to-b from-rose-200 to-rose-100 text-rose-700 dark:from-rose-800/50 dark:to-rose-900/60 dark:text-rose-300"
              }
            >
              {isSuccess ? (
                <CheckCircle className="h-3.5 w-3.5" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5" />
              )}
              {isSuccess ? 'Tool executed successfully' : 'Tool execution failed'}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-0 h-full flex-1 overflow-hidden relative">
        {isStreaming && !parsedToolOutput ? (
          <LoadingState
            icon={FileText}
            iconColor="text-purple-500 dark:text-purple-400"
            bgColor="bg-gradient-to-b from-purple-100 to-purple-50 shadow-inner dark:from-purple-800/40 dark:to-purple-900/60 dark:shadow-purple-950/20"
            title="Generating document"
            filePath={name}
            showProgress={true}
          />
        ) : parsedToolOutput ? (
          <ScrollArea className="h-full w-full">
            <div className="p-4 space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Status</p>
                <p className="text-sm text-zinc-800 dark:text-zinc-200">{displayMessage}</p>
              </div>

              {documentPath && (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Generated Document</p>
                  <div className="flex items-center gap-3 p-3 bg-muted/30 border rounded-lg">
                    <DownloadCloud className="h-6 w-6 text-purple-500 flex-shrink-0" />
                    <div className="flex-grow">
                      <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 break-all">{fileName}</p>
                      {/* <p className="text-xs text-zinc-500 dark:text-zinc-400 break-all">{documentPath}</p> */}
                    </div>
                    {canDirectlyLink ? (
                       <Button variant="outline" size="sm" asChild className="bg-white dark:bg-zinc-800">
                        <a href={documentPath} target="_blank" rel="noopener noreferrer">
                          View/Download
                        </a>
                      </Button>
                    ) : (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button variant="outline" size="sm" disabled className="bg-white dark:bg-zinc-800">
                              Download (Not Implemented)
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>Direct download from this path is not yet supported.</p>
                            <p>Path: {documentPath}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                      // Potentially use FileRenderer here if we had a binaryUrl
                      // <FileRenderer fileName={fileName} binaryUrl={documentPath_as_binary_url_if_available} content={null} />
                    )}
                  </div>
                </div>
              )}

              {/* Display input parameters if available from assistantContent */}
              {assistantContent && (
                <details className="group">
                  <summary className="text-sm font-medium text-zinc-700 dark:text-zinc-300 cursor-pointer group-hover:text-purple-600 dark:group-hover:text-purple-400">
                    View Input Parameters
                  </summary>
                  <div className="mt-2 border-muted bg-muted/20 rounded-lg overflow-hidden border">
                    <div className="p-4">
                      <pre className="text-xs text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap break-words font-mono">
                        {JSON.stringify(extractToolData(assistantContent).toolResult?.arguments || {"message": "No input parameters found or assistant content not structured as tool call."}, null, 2)}
                      </pre>
                    </div>
                  </div>
                </details>
              )}

            </div>
          </ScrollArea>
        ) : (
          <div className="flex flex-col items-center justify-center h-full py-12 px-6 bg-gradient-to-b from-white to-zinc-50 dark:from-zinc-950 dark:to-zinc-900">
            <div className="w-20 h-20 rounded-full flex items-center justify-center mb-6 bg-gradient-to-b from-zinc-100 to-zinc-50 shadow-inner dark:from-zinc-800/40 dark:to-zinc-900/60">
              <Wrench className="h-10 w-10 text-zinc-400 dark:text-zinc-600" />
            </div>
            <h3 className="text-xl font-semibold mb-2 text-zinc-900 dark:text-zinc-100">
              No Tool Output
            </h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 text-center max-w-md">
              The tool did not produce any output to display.
            </p>
          </div>
        )}
      </CardContent>

      <div className="px-4 py-2 h-10 bg-gradient-to-r from-zinc-50/90 to-zinc-100/90 dark:from-zinc-900/90 dark:to-zinc-800/90 backdrop-blur-sm border-t border-zinc-200 dark:border-zinc-800 flex justify-between items-center gap-4">
        <div className="h-full flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
          {!isStreaming && parsedToolOutput && (
            <Badge variant="outline" className="h-6 py-0.5 bg-zinc-50 dark:bg-zinc-900">
              <FileText className="h-3 w-3" />
              Document Tool
            </Badge>
          )}
        </div>

        <div className="text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-2">
          {/* <Clock className="h-3.5 w-3.5" /> */}
          {toolTimestamp && !isStreaming
            ? formatTimestamp(toolTimestamp)
            : assistantTimestamp
              ? formatTimestamp(assistantTimestamp)
              : ''}
        </div>
      </div>
    </Card>
  );
}

// Minimal TooltipProvider and Tooltip components if not already globally available or for simplicity
// In a real app, these would come from your UI library (e.g., Shadcn UI)

const TooltipProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <>{children}</>;
};

const Tooltip: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Basic div wrapper, actual tooltip behavior would need more
  return <div className="relative inline-block">{children}</div>;
};

const TooltipTrigger: React.FC<{ children: React.ReactNode, asChild?: boolean }> = ({ children }) => {
  // Basic div wrapper
  return <div className="inline-block">{children}</div>;
};

const TooltipContent: React.FC<{ children: React.ReactNode, side?: string }> = ({ children }) => {
  // Basic styling for a tooltip, very rudimentary
  // A real implementation would handle positioning, visibility, etc.
  // This is just a placeholder to make the component compile.
  return (
    <div className="absolute z-10 invisible group-hover:visible bg-black text-white text-xs rounded py-1 px-2 left-1/2 -translate-x-1/2 mt-1">
      {children}
    </div>
  );
};

export default DocumentGenerationToolView;
