import React from 'react';

export function formatPassageText(text: string): React.ReactNode {
  // Match curly single quote pairs (\u2018...\u2019) and markdown italics (*...*)
  const pattern = /(\u2018[^\u2019]+\u2019|\*[^*]+\*)/g;
  const parts = text.split(pattern);
  if (parts.length === 1) return text;

  return parts.map((part, i) => {
    if (part.startsWith('\u2018') && part.endsWith('\u2019')) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}
