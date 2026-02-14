import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import styled from 'styled-components';

const MarkdownWrapper = styled.div`
  font-family: 'Georgia', serif;
  line-height: 1.85;
  text-align: justify;
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

interface MarkdownMessageProps {
  content: string;
}

const MarkdownMessage: React.FC<MarkdownMessageProps> = React.memo(({ content }) => {
  return (
    <MarkdownWrapper>
      <ReactMarkdown rehypePlugins={[rehypeRaw]}>{content}</ReactMarkdown>
    </MarkdownWrapper>
  );
});

MarkdownMessage.displayName = 'MarkdownMessage';

export default MarkdownMessage;
