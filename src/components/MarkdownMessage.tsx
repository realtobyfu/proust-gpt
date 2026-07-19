import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import styled from 'styled-components';
import type { Passage } from '../hooks/useStreamingQuery';

const MarkdownWrapper = styled.div`
  font-family: 'Georgia', serif;
  line-height: 1.85;
  text-align: justify;
  hyphens: auto;
  color: inherit;

  p {
    margin: 0 0 1em 0;

    &:last-child {
      margin-bottom: 0;
    }
  }

  em {
    font-style: italic;
  }

  strong {
    font-weight: 600;
  }

  /* Degrade headings to plain text */
  h1, h2, h3, h4, h5, h6 {
    font-size: inherit;
    font-weight: inherit;
    margin: 0 0 0.8em 0;
  }

  /* Degrade lists to plain paragraphs */
  ul, ol {
    list-style: none;
    padding: 0;
    margin: 0 0 0.8em 0;
  }

  li {
    margin: 0;
    padding: 0;

    &::before {
      content: none;
    }
  }

  blockquote {
    margin: 0.5em 0;
    padding-left: 1em;
    border-left: 2px solid #c4a882;
    font-style: italic;
  }

  code {
    font-family: inherit;
    font-size: inherit;
  }

  pre {
    font-family: inherit;
    white-space: pre-wrap;
  }

  a {
    color: #8b4513;
    text-decoration: underline;
  }

  hr {
    border: none;
    border-top: 1px solid #e0d8cf;
    margin: 1em 0;
  }
`;

const CitationRef = styled.span`
  display: inline;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.7em;
  font-weight: 600;
  color: #8b4513;
  cursor: pointer;
  vertical-align: super;
  line-height: 1;
  padding: 0 0.15em;
  border-radius: 2px;
  transition: background 0.15s ease, color 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.12);
    color: #6b3410;
  }
`;

interface MarkdownMessageProps {
  content: string;
  passages?: Passage[];
  onCitationClick?: (citationIndex: number) => void;
}

const MarkdownMessage: React.FC<MarkdownMessageProps> = React.memo(({ content, passages, onCitationClick }) => {
  // Build set of valid citation indices from passages
  const validIndices = useMemo(() => {
    if (!passages) return new Set<number>();
    return new Set(passages.map(p => p.citation_index).filter((n): n is number => n != null));
  }, [passages]);

  // Pre-process content: replace [N] with HTML cite-ref tags (only for valid indices)
  const processedContent = useMemo(() => {
    if (validIndices.size === 0) return content;
    return content.replace(/\[(\d+)\]/g, (match, digit) => {
      const n = parseInt(digit, 10);
      if (validIndices.has(n)) {
        return `<cite-ref data-n="${n}">[${n}]</cite-ref>`;
      }
      return match;
    });
  }, [content, validIndices]);

  return (
    <MarkdownWrapper>
      <ReactMarkdown
        rehypePlugins={[rehypeRaw]}
        components={{
          'cite-ref': ({ node, ...props }) => {
            const n = parseInt((props as Record<string, string>)['data-n'], 10);
            const activate = () => onCitationClick?.(n);
            return (
              <CitationRef
                role="button"
                tabIndex={0}
                aria-label={`Passage ${n}`}
                onClick={(e) => {
                  e.stopPropagation();
                  activate();
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.stopPropagation();
                    activate();
                  }
                }}
                title={`Passage ${n}`}
              >
                [{n}]
              </CitationRef>
            );
          },
        } as Record<string, React.ComponentType<any>>}
      >
        {processedContent}
      </ReactMarkdown>
    </MarkdownWrapper>
  );
});

MarkdownMessage.displayName = 'MarkdownMessage';

export default MarkdownMessage;
