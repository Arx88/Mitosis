import { cn } from '@/lib/utils';
// import { marked } from 'marked'; // Not needed anymore
import { memo, useId, useMemo } from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock, CodeBlockCode } from '@/components/ui/code-block';
import { ReasoningView } from '@/components/thread/ReasoningView'; // Import ReasoningView

export type MarkdownProps = {
  children: string;
  id?: string;
  className?: string;
  components?: Partial<Components>;
};

// Define the data structure for extracted thoughts
interface ExtractedThought {
  id: string;
  content: string;
}

// function parseMarkdownIntoBlocks(markdown: string): string[] {
//   const tokens = marked.lexer(markdown);
//   return tokens.map((token: any) => token.raw);
// } // Removed as we will process the whole markdown

function extractLanguage(className?: string): string {
  if (!className) return 'plaintext';
  const match = className.match(/language-(\w+)/);
  return match ? match[1] : 'plaintext';
}

const INITIAL_COMPONENTS: Partial<Components> = {
  code: function CodeComponent({ className, children, ...props }: any) {
    const isInline =
      !props.node?.position?.start.line ||
      props.node?.position?.start.line === props.node?.position?.end.line;

    if (isInline) {
      return (
        <span
          className={cn(
            'bg-primary-foreground dark:bg-zinc-800 dark:border dark:border-zinc-700 rounded-sm px-1 font-mono text-sm',
            className,
          )}
          {...props}
        >
          {children}
        </span>
      );
    }

    const language = extractLanguage(className);

    return (
      <CodeBlock className="rounded-md overflow-hidden my-4 border border-zinc-200 dark:border-zinc-800 max-w-full min-w-0 w-full">
        <CodeBlockCode
          code={children as string}
          language={language}
          className="text-sm"
        />
      </CodeBlock>
    );
  },
  pre: function PreComponent({ children }: any) {
    return <>{children}</>;
  },
  ul: function UnorderedList({ children, ...props }: any) {
    return (
      <ul className="list-disc pl-5 my-2" {...props}>
        {children}
      </ul>
    );
  },
  ol: function OrderedList({ children, ...props }: any) {
    return (
      <ol className="list-decimal pl-5 my-2" {...props}>
        {children}
      </ol>
    );
  },
  li: function ListItem({ children, ...props }: any) {
    return (
      <li className="my-1" {...props}>
        {children}
      </li>
    );
  },
  h1: function H1({ children, ...props }: any) {
    return (
      <h1 className="text-2xl font-bold my-3" {...props}>
        {children}
      </h1>
    );
  },
  h2: function H2({ children, ...props }: any) {
    return (
      <h2 className="text-xl font-bold my-2" {...props}>
        {children}
      </h2>
    );
  },
  h3: function H3({ children, ...props }: any) {
    return (
      <h3 className="text-lg font-bold my-2" {...props}>
        {children}
      </h3>
    );
  },
  blockquote: function Blockquote({ children, ...props }: any) {
    return (
      <blockquote
        className="border-l-4 border-muted pl-4 italic my-2 dark:text-zinc-400 dark:border-zinc-600"
        {...props}
      >
        {children}
      </blockquote>
    );
  },
  a: function Anchor({ children, href, ...props }: any) {
    return (
      <a
        href={href}
        className="text-primary hover:underline dark:text-blue-400"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    );
  },
  table: function Table({ children, ...props }: any) {
    return (
      <table className="w-full border-collapse my-3 text-sm" {...props}>
        {children}
      </table>
    );
  },
  th: function TableHeader({ children, ...props }: any) {
    return (
      <th
        className="border border-slate-300 dark:border-zinc-700 px-3 py-2 text-left font-semibold bg-slate-100 dark:bg-zinc-800"
        {...props}
      >
        {children}
      </th>
    );
  },
  td: function TableCell({ children, ...props }: any) {
    return (
      <td
        className="border border-slate-300 dark:border-zinc-700 px-3 py-2"
        {...props}
      >
        {children}
      </td>
    );
  },
  // p: handled dynamically below
};

// This memoization might need reconsideration if extractedThoughts makes props change too often.
// For now, removing MemoizedMarkdownBlock and parsing directly in MarkdownComponent.
// const MemoizedMarkdownBlock = memo(
//   function MarkdownBlock({
//     content,
//     components = INITIAL_COMPONENTS,
//   }: {
//     content: string;
//     components?: Partial<Components>;
//   }) {
//     return (
//       <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
//         {content}
//       </ReactMarkdown>
//     );
//   },
//   function propsAreEqual(prevProps: any, nextProps: any) {
//     return prevProps.content === nextProps.content;
//   },
// );
// MemoizedMarkdownBlock.displayName = 'MemoizedMarkdownBlock';

function MarkdownComponent({
  children,
  // id, // id might not be needed per block anymore if we don't split
  className,
  components: propComponents, // User-provided components
}: MarkdownProps) {
  // const generatedId = useId(); // May not be needed for the main component id
  // const blockId = id ?? generatedId; // Not needed if not splitting into blocks

  const { processedMarkdown, extractedThoughts } = useMemo(() => {
    const thoughts: ExtractedThought[] = [];
    let markdown = children;
    const thinkRegex = /<think>((?:.|\n)*?)<\/think>/g;
    let match;
    let index = 0;
    while ((match = thinkRegex.exec(markdown)) !== null) {
      const id = `reasoning-view-${index++}`;
      thoughts.push({ id, content: match[1] });
      markdown = markdown.replace(match[0], `<p>${id}</p>`);
    }
    return { processedMarkdown: markdown, extractedThoughts: thoughts };
  }, [children]);

  const combinedComponents = useMemo(() => {
    const componentsWithCustomP: Partial<Components> = {
      ...INITIAL_COMPONENTS,
      p: ({ node, children: pChildren, ...props }: any) => {
        const childText =
          pChildren && typeof pChildren[0] === 'string' ? pChildren[0] : '';
        const thought = extractedThoughts.find(t => t.id === childText);
        if (thought) {
          return <ReasoningView content={thought.content} />;
        }

        // It's not a thought placeholder, render a normal paragraph or user-defined component
        if (propComponents?.p && typeof propComponents.p === 'function') {
          return propComponents.p({ node, children: pChildren, ...props });
        }
        // If propComponents.p is not a function (e.g., undefined or a string like "p"),
        // render a standard HTML paragraph.
        return <p {...props}>{pChildren}</p>;
      },
      // Potentially merge other propComponents here if needed
    };

    // Corrected merge strategy:
    // 1. Start with INITIAL_COMPONENTS.
    // 2. Allow propComponents to override any of these.
    // 3. Ensure our custom 'p' (from componentsWithCustomP.p) is used.
    //    Our custom 'p' already handles deferring to propComponents.p if it's not a thought.
    return { ...INITIAL_COMPONENTS, ...propComponents, p: componentsWithCustomP.p };
  }, [extractedThoughts, propComponents]);

  return (
    <div
      className={cn(
        'prose-code:before:hidden prose-code:after:hidden',
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={combinedComponents}
      >
        {processedMarkdown}
      </ReactMarkdown>
    </div>
  );
}

const Markdown = memo(MarkdownComponent);
Markdown.displayName = 'Markdown';

export { Markdown };
