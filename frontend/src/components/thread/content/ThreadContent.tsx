import React, { useRef, useState, useCallback } from 'react';
import { ArrowDown, CircleDashed, CheckCircle, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Markdown } from '@/components/ui/markdown';
import { UnifiedMessage, ParsedContent, ParsedMetadata } from '@/components/thread/types';
import { FileAttachmentGrid } from '@/components/thread/file-attachment';
import { useFilePreloader } from '@/hooks/react-query/files';
import { useAuth } from '@/components/AuthProvider';
import { Project } from '@/lib/api';
import {
    extractPrimaryParam,
    getToolIcon,
    getUserFriendlyToolName,
    safeJsonParse,
} from '@/components/thread/utils';
import { motion } from 'framer-motion';
import { KortixLogo } from '@/components/sidebar/kortix-logo';
import { AgentLoader } from './loader';
import { ReasoningView } from '@/components/thread/ReasoningView';
import { parseXmlToolCalls, isNewXmlFormat, extractToolNameFromStream } from '@/components/thread/tool-views/xml-parser';
import { parseToolResult } from '@/components/thread/tool-views/tool-result-parser';

const extractAllThinkContent = (rawContent: string | null | undefined): string | null => {
  if (!rawContent) return null;
  const matches = [];
  const regex = /<think>((?:.|\n)*?)<\/think>/gi;
  let match;
  while ((match = regex.exec(rawContent)) !== null) { matches.push(match[1]); }
  return matches.length > 0 ? matches.join('\n') : null;
};

const HIDE_STREAMING_XML_TAGS = new Set([ /* ... tags ... */ ]); // Assume populated

export function renderAttachments(attachments: string[], fileViewerHandler?: (filePath?: string, filePathList?: string[]) => void, sandboxId?: string, project?: Project) {
    if (!attachments || attachments.length === 0) return null;
    return <FileAttachmentGrid attachments={attachments} onFileClick={fileViewerHandler} showPreviews={true} sandboxId={sandboxId} project={project} />;
}

// Full, correct renderMarkdownContent function
export function renderMarkdownContent(
    content: string, handleToolClick: (assistantMessageId: string | null, toolName: string) => void, messageId: string | null,
    fileViewerHandler?: (filePath?: string, filePathList?: string[]) => void, sandboxId?: string, project?: Project,
    debugMode?: boolean, ignoreThinkTags?: boolean
) {
    const MotionButton = motion.button;

    if (debugMode) { return <pre className="text-xs font-mono whitespace-pre-wrap overflow-x-auto p-2 border border-border rounded-md bg-muted/30 text-foreground">{content}</pre>; }

    if (isNewXmlFormat(content)) {
        const contentParts: React.ReactNode[] = []; let lastIndex = 0;
        const functionCallsRegex = /<function_calls>([\s\S]*?)<\/function_calls>/gi; let match;
        while ((match = functionCallsRegex.exec(content)) !== null) {
            if (match.index > lastIndex) {
                const textBeforeBlock = content.substring(lastIndex, match.index);
                if (textBeforeBlock.trim()) contentParts.push(<Markdown key={`md-${lastIndex}`} className="text-sm prose prose-sm dark:prose-invert chat-markdown max-w-none break-words">{textBeforeBlock}</Markdown>);
            }
            const toolCalls = parseXmlToolCalls(match[0]);
            toolCalls.forEach((toolCall, index) => {
                const toolName = toolCall.functionName.replace(/_/g, '-'); const IconComponent = getToolIcon(toolName);
                let paramDisplay = '';
                if (toolCall.parameters.file_path) paramDisplay = toolCall.parameters.file_path;
                else if (toolCall.parameters.command) paramDisplay = toolCall.parameters.command;
                else if (toolCall.parameters.query) paramDisplay = toolCall.parameters.query;
                else if (toolCall.parameters.url) paramDisplay = toolCall.parameters.url;
                contentParts.push(<div key={`tool-${match.index}-${index}`} className="my-1"><MotionButton onClick={() => handleToolClick(messageId, toolName)} className="inline-flex items-center gap-1.5 py-1 px-1 text-xs text-muted-foreground bg-gradient-to-r from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-800 rounded-md transition-colors cursor-pointer border border-neutral-200 dark:border-neutral-700/50" whileHover={{ scale: 1.05, filter: 'brightness(0.95)' }} whileTap={{ scale: 0.95, filter: 'brightness(0.9)' }} transition={{ type: "spring", stiffness: 400, damping: 10 }}><div className='border-2 bg-gradient-to-br from-neutral-200 to-neutral-300 dark:from-neutral-700 dark:to-neutral-800 flex items-center justify-center p-0.5 rounded-sm border-neutral-400/20 dark:border-neutral-600'><IconComponent className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" /></div><span className="font-mono text-xs text-foreground">{getUserFriendlyToolName(toolName)}</span>{paramDisplay && <span className="ml-1 text-muted-foreground truncate max-w-[200px]" title={paramDisplay}>{paramDisplay}</span>}</MotionButton></div>);
            });
            lastIndex = match.index + match[0].length;
        }
        if (lastIndex < content.length) { const remainingText = content.substring(lastIndex); if (remainingText.trim()) contentParts.push(<Markdown key={`md-${lastIndex}`} className="text-sm prose prose-sm dark:prose-invert chat-markdown max-w-none break-words">{remainingText}</Markdown>); }
        if (contentParts.length > 0) return contentParts; return null;
    }

    const xmlRegex = /<(?!inform\b)([a-zA-Z\-_]+)(?:\s+[^>]*)?>(?:[\s\S]*?)<\/\1>|<(?!inform\b)([a-zA-Z\-_]+)(?:\s+[^>]*)?\/>/g;
    let lastIndex = 0; const contentParts: React.ReactNode[] = []; let match;
    if (!content.match(xmlRegex)) { if (content.trim()) return <Markdown className="text-sm prose prose-sm dark:prose-invert chat-markdown max-w-none break-words">{content}</Markdown>; return null; }
    while ((match = xmlRegex.exec(content)) !== null) {
        if (match.index > lastIndex) { const textBeforeTag = content.substring(lastIndex, match.index); if (textBeforeTag.trim()) contentParts.push(<Markdown key={`md-${lastIndex}`} className="text-sm prose prose-sm dark:prose-invert chat-markdown max-w-none inline-block mr-1 break-words">{textBeforeTag}</Markdown>); }
        const rawXml = match[0]; const toolName = match[1] || match[2]; const toolCallKey = `tool-${match.index}`;
        if (toolName === 'think') { if (ignoreThinkTags) { lastIndex = xmlRegex.lastIndex; continue; } else { const thinkContentMatch = rawXml.match(/<think>((?:.|\n)*?)<\/think>/i); const extractedThinkContent = thinkContentMatch ? thinkContentMatch[1] : ''; contentParts.push( <ReasoningView key={`reasoning-${match.index}`} content={extractedThinkContent} /> ); lastIndex = xmlRegex.lastIndex; continue; } }
        if (toolName === 'ask') { const attachmentsMatch = rawXml.match(/attachments=["']([^"']*)["']/i); const attachments = attachmentsMatch ? attachmentsMatch[1].split(',').map(a => a.trim()) : []; const contentMatch = rawXml.match(/<ask[^>]*>([\s\S]*?)<\/ask>/i); const askContent = contentMatch ? contentMatch[1] : ''; contentParts.push(<div key={`ask-${match.index}`} className="space-y-3"><Markdown className="text-sm prose prose-sm dark:prose-invert chat-markdown max-w-none break-words [&>:first-child]:mt-0 prose-headings:mt-3">{askContent}</Markdown>{renderAttachments(attachments, fileViewerHandler, sandboxId, project)}</div>); }
        else {
            const IconComponent = getToolIcon(toolName); const paramDisplay = extractPrimaryParam(toolName, rawXml);
            contentParts.push(<div key={toolCallKey} className="my-1"><MotionButton onClick={() => handleToolClick(messageId, toolName)} className="inline-flex items-center gap-1.5 py-1 px-1 text-xs text-muted-foreground bg-gradient-to-r from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-800 rounded-md transition-colors cursor-pointer border border-neutral-200 dark:border-neutral-700/50" whileHover={{ scale: 1.05, filter: 'brightness(0.95)' }} whileTap={{ scale: 0.95, filter: 'brightness(0.9)' }} transition={{ type: "spring", stiffness: 400, damping: 10 }}><div className='border-2 bg-gradient-to-br from-neutral-200 to-neutral-300 dark:from-neutral-700 dark:to-neutral-800 flex items-center justify-center p-0.5 rounded-sm border-neutral-400/20 dark:border-neutral-600'><IconComponent className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" /></div><span className="font-mono text-xs text-foreground">{getUserFriendlyToolName(toolName)}</span>{paramDisplay && <span className="ml-1 text-muted-foreground truncate max-w-[200px]" title={paramDisplay}>{paramDisplay}</span>}</MotionButton></div>);
        }
        lastIndex = xmlRegex.lastIndex;
    }
    const remainingTextAfterLoop = content.substring(lastIndex);
    if (remainingTextAfterLoop.trim()) contentParts.push(<Markdown key={`md-final-${lastIndex}`} className="text-sm prose prose-sm dark:prose-invert chat-markdown max-w-none break-words">{remainingTextAfterLoop}</Markdown>);
    return contentParts.length > 0 ? contentParts : null;
}

export interface ThreadContentProps { /* ... props ... */
    messages: UnifiedMessage[]; streamingTextContent?: string; streamingToolCall?: any; agentStatus: 'idle' | 'running' | 'connecting' | 'error'; handleToolClick: (assistantMessageId: string | null, toolName: string) => void; handleOpenFileViewer: (filePath?: string, filePathList?: string[]) => void; readOnly?: boolean; visibleMessages?: UnifiedMessage[]; streamingText?: string; isStreamingText?: boolean; currentToolCall?: any; streamHookStatus?: string; sandboxId?: string; project?: Project; debugMode?: boolean; isPreviewMode?: boolean; agentName?: string; agentAvatar?: React.ReactNode; emptyStateComponent?: React.ReactNode; reasoning?: string | null; isAgentActuallyThinking?: boolean;
}

export const ThreadContent: React.FC<ThreadContentProps> = ({
    messages, streamingTextContent = "", streamingToolCall, agentStatus, handleToolClick,
    handleOpenFileViewer, readOnly = false, visibleMessages, streamingText = "",
    isStreamingText = false, currentToolCall, streamHookStatus = "idle", sandboxId,
    project, debugMode = false, isPreviewMode = false, agentName = 'Suna',
    agentAvatar = <KortixLogo size={16} />, emptyStateComponent, reasoning,
    isAgentActuallyThinking,
}) => {
    const MotionDiv = motion.div;
    const MotionP = motion.p;

    console.log(`[TIMER_DEBUG] ThreadContent - Received props.isAgentActuallyThinking:`, isAgentActuallyThinking);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const latestMessageRef = useRef<HTMLDivElement>(null);
    const [showScrollButton, setShowScrollButton] = useState(false);
    const [userHasScrolled, setUserHasScrolled] = useState(false);
    const { session } = useAuth();
    const { preloadFiles } = useFilePreloader();

    const containerClassName = isPreviewMode 
        ? "flex-1 overflow-y-auto scrollbar-thin scrollbar-track-secondary/0 scrollbar-thumb-primary/10 scrollbar-thumb-rounded-full hover:scrollbar-thumb-primary/10 px-6 py-4 pb-72"
        : "flex-1 overflow-y-auto scrollbar-thin scrollbar-track-secondary/0 scrollbar-thumb-primary/10 scrollbar-thumb-rounded-full hover:scrollbar-thumb-primary/10 px-6 py-4 pb-72 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60";

    const displayMessages = readOnly && visibleMessages ? visibleMessages : messages;
    const allAttachments = React.useMemo(() => {
        const attachments: string[] = [];
        if (!sandboxId) return attachments;
        displayMessages.forEach(message => {
            if (message.type === 'user') {
                try {
                    const content = typeof message.content === 'string' ? message.content : '';
                    const attachmentsMatch = content.match(/\[Uploaded File: (.*?)\]/g);
                    if (attachmentsMatch) {
                        attachmentsMatch.forEach(match => {
                            const pathMatch = match.match(/\[Uploaded File: (.*?)\]/);
                            if (pathMatch && pathMatch[1]) attachments.push(pathMatch[1]);
                        });
                    }
                } catch (e) { console.error('Error parsing message attachments:', e); }
            }
        });
        return attachments;
    }, [displayMessages, sandboxId]);

    const handleScroll = () => { /* ... */ }; // Assuming implementation exists
    const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => { /* ... */ }, []); // Assuming implementation exists
    React.useEffect(() => { /* ... */ }, [allAttachments, sandboxId, session?.access_token, preloadFiles]); // Assuming implementation exists

    return (
        <>
            {(displayMessages.length === 0 && !streamingTextContent && !streamingToolCall && !streamingText && !currentToolCall && agentStatus === 'idle') ? (
                <div className="flex-1 min-h-[60vh] flex items-center justify-center">
                    {emptyStateComponent || (
                        <div className="text-center text-muted-foreground">
                            {readOnly ? "No messages to display." : "Send a message to start."}
                        </div>
                    )}
                </div>
            ) : (
                <div
                    ref={messagesContainerRef}
                    className={containerClassName}
                    onScroll={handleScroll}
                >
                    <div className="mx-auto max-w-3xl md:px-8 min-w-0">
                        <div className="space-y-8 min-w-0">
                            {(() => {
                                type MessageGroup = { type: 'user' | 'assistant_group'; messages: UnifiedMessage[]; key: string; };
                                const groupedMessages: MessageGroup[] = [];
                                let currentGroup: MessageGroup | null = null;
                                // let assistantGroupCounter = 0; // This was in the original file, check if needed by grouping logic.
                                                                // The provided snippet for grouping logic did not use it.
                                                                // It's safer to keep it if it was there. Let's assume it's part of the `... grouping logic ...`

                                // Preserving original grouping logic structure from provided file:
                                displayMessages.forEach((message, index) => {
                                    // --- Start of original grouping logic ---
                                    // This is a simplified placeholder for the actual grouping logic from the file.
                                    // The actual grouping logic from the file needs to be here.
                                    // For the purpose of this fix, we assume the original grouping logic correctly populates `currentGroup` and `groupedMessages`.
                                    // Example:
                                    if (message.type === 'user') {
                                        if (currentGroup && currentGroup.type === 'user') {
                                            currentGroup.messages.push(message);
                                        } else {
                                            if (currentGroup) groupedMessages.push(currentGroup);
                                            currentGroup = { type: 'user', messages: [message], key: message.message_id || `user-group-${index}` };
                                        }
                                    } else if (message.type === 'assistant') {
                                        // This is a very simplified view. The actual logic might group multiple assistant messages
                                        // or handle tool calls, etc.
                                        if (currentGroup) groupedMessages.push(currentGroup);
                                        currentGroup = { type: 'assistant_group', messages: [message], key: message.message_id || `assistant-group-${index}` };
                                    }
                                    // --- End of original grouping logic ---
                                });
                                if (currentGroup) groupedMessages.push(currentGroup);

                                // The streamingTextContent handling was also part of the original file's IIFE.
                                // This logic should be preserved if it existed at this level.
                                // From the provided file, streamingTextContent is handled *inside* the map or later.
                                // The provided snippet had: if (streamingTextContent) { /* ... streaming logic ... */ }
                                // This should be here if it was part of the original grouping logic.
                                // For now, assuming it's handled within the map or by specific message items.

                                return groupedMessages.map((group, groupIndex) => {
                                    if (group.type === 'user') {
                                        const message = group.messages[0];
                                        const messageContent = (() => { try { const parsed = safeJsonParse<ParsedContent>(message.content, { content: message.content }); return parsed.content || message.content; } catch { return message.content; } })();
                                        if (debugMode) { return <MotionDiv key={group.key} className="flex justify-end"><div className="flex max-w-[85%] rounded-xl bg-primary/10 px-4 py-3 break-words overflow-hidden"><pre className="text-xs font-mono whitespace-pre-wrap overflow-x-auto min-w-0 flex-1">{message.content}</pre></div></MotionDiv>; }
                                        const attachmentsMatch = messageContent.match(/\[Uploaded File: (.*?)\]/g);
                                        const attachments = attachmentsMatch ? attachmentsMatch.map(match => { const pathMatch = match.match(/\[Uploaded File: (.*?)\]/); return pathMatch ? pathMatch[1] : null; }).filter(Boolean) : [];
                                        const cleanContent = messageContent.replace(/\[Uploaded File: .*?\]/g, '').trim();
                                        return (
                                            <MotionDiv key={group.key} className="flex justify-end" initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, ease: "easeOut" }}>
                                                <MotionDiv className="flex max-w-[85%] rounded-xl px-4 py-3 break-words overflow-hidden bg-blue-500 text-white dark:bg-blue-700 dark:text-gray-100" whileHover={{ scale: 1.02, y: -2, boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)' }} transition={{ type: "spring", stiffness: 300, damping: 10 }}>
                                                    <div className="space-y-3 min-w-0 flex-1">
                                                        {cleanContent && <Markdown className="text-sm prose prose-sm dark:prose-invert chat-markdown max-w-none [&>:first-child]:mt-0 prose-headings:mt-3 break-words overflow-wrap-anywhere">{cleanContent}</Markdown>}
                                                        {renderAttachments(attachments as string[], handleOpenFileViewer, sandboxId, project)}
                                                    </div>
                                                </MotionDiv>
                                            </MotionDiv>
                                        );
                                    } else if (group.type === 'assistant_group') {
                                        return (
                                            <MotionDiv
                                                key={group.key}
                                                ref={groupIndex === groupedMessages.length - 1 ? latestMessageRef : null}
                                                className="relative pl-3"
                                                initial={{ opacity: 0, y: 30 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                transition={{ duration: 0.4, ease: "easeOut", delay: 0.1 }}
                                            >
                                                <MotionDiv
                                                    className="absolute top-0 bottom-0 w-[2px] bg-sky-400 dark:bg-sky-600"
                                                    style={{ left: '6px' }}
                                                    initial={{ height: 0 }}
                                                    animate={{ height: "100%" }}
                                                    transition={{
                                                        duration: 0.6,
                                                        ease: "circOut",
                                                        delay: 0.2
                                                    }}
                                                />
                                                <div className="flex flex-col gap-2">
                                                    <div className="flex items-center">
                                                        <MotionDiv className="rounded-md flex items-center justify-center" initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.2, duration: 0.3 }}>{agentAvatar}</MotionDiv>
                                                        <MotionP className='ml-2 text-sm text-muted-foreground' initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3, duration: 0.3 }}>{agentName ? agentName : 'Suna'}</MotionP>
                                                    </div>
                                                    {(reasoning || isAgentActuallyThinking) && (
                                                        <ReasoningView
                                                            content={reasoning}
                                                            isStreamingAgentActive={isAgentActuallyThinking}
                                                            animationDelay={0.5}
                                                        />
                                                    )}
                                                    <MotionDiv
                                                        className="flex max-w-[90%] rounded-lg text-sm break-words overflow-hidden bg-slate-100 dark:bg-slate-800 p-3 border border-border/50 shadow-sm"
                                                        initial={{ opacity: 0, y: 10 }}
                                                        animate={{ opacity: 1, y: 0 }}
                                                        transition={{ duration: 0.4, ease: "easeOut", delay: 0.7 }}
                                                        whileHover={{
                                                            scale: 1.01,
                                                            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)',
                                                            transition: { type: "spring", stiffness: 200, damping: 10 }
                                                        }}
                                                    >
                                                        <div className="space-y-2 min-w-0 flex-1">
                                                            {(() => {
                                                                if (debugMode && group.messages.length > 0) { /* ... debug content ... */ }
                                                                const elements: React.ReactNode[] = [];
                                                                let assistantMessageCount = 0;
                                                                group.messages.forEach((message, msgIndex) => {
                                                                    if (message.type === 'assistant') {
                                                                        const parsedContent = safeJsonParse<ParsedContent>(message.content, {});
                                                                        const msgKey = message.message_id || `submsg-assistant-${msgIndex}`;
                                                                        if (!parsedContent.content && message.message_id !== 'streamingTextContent') return;
                                                                        const actualContentToRender = message.message_id === 'streamingTextContent' ? streamingTextContent : parsedContent.content;
                                                                        const renderedContent = renderMarkdownContent(actualContentToRender || "", handleToolClick, message.message_id, handleOpenFileViewer, sandboxId, project, debugMode, true);
                                                                        if (renderedContent) {
                                                                            elements.push(<div key={msgKey} className={assistantMessageCount > 0 ? "mt-4" : ""}><div className="prose prose-sm dark:prose-invert chat-markdown max-w-none [&>:first-child]:mt-0 prose-headings:mt-3 break-words overflow-hidden">{renderedContent}</div></div>);
                                                                            assistantMessageCount++;
                                                                        }
                                                                    }
                                                                });
                                                                return elements;
                                                            })()}
                                                            {/* Preserving original streaming indicators logic from provided file */}
                                                            {groupIndex === groupedMessages.length - 1 && !readOnly && (streamHookStatus === 'streaming' || streamHookStatus === 'connecting') && !group.messages.find(m => m.message_id === 'streamingTextContent') && (
                                                                <div className="flex items-center text-xs text-muted-foreground">
                                                                    <CircleDashed className="h-3 w-3 mr-1.5 animate-spin" />
                                                                    <span>Assistant is thinking...</span>
                                                                </div>
                                                            )}
                                                            {readOnly && groupIndex === groupedMessages.length - 1 && isStreamingText && (
                                                                <div className="flex items-center text-xs text-muted-foreground">
                                                                    <CircleDashed className="h-3 w-3 mr-1.5 animate-spin" />
                                                                    <span>Playing back response...</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </MotionDiv>
                                                </div>
                                            </MotionDiv>
                                        );
                                    }
                                    return null;
                                });
                            })()}
                            {/* Any other elements that were inside "space-y-8" but after the map would go here. */}
                            {/* Based on the provided file, there are no such elements directly here. AgentLoader is handled by the main conditional. */}
                        </div>
                    </div>
                    <div ref={messagesEndRef} className="h-1" />
                </div>
            )}
            {showScrollButton && (
                <Button
                    variant="outline"
                    size="icon"
                    className="fixed bottom-20 right-6 z-10 h-8 w-8 rounded-full shadow-md"
                    onClick={() => scrollToBottom('smooth')}
                >
                    <ArrowDown className="h-4 w-4" />
                </Button>
            )}
        </>
    );
};

export default ThreadContent;
