import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Assistant and tool text can contain Markdown. Keep HTML inert and constrain
// wide content to the chat bubble instead of letting it stretch the panel.
const components = {
  table: ({ node: _node, ...props }) => (
    <div className="chat-table-scroll" role="region" aria-label="Response table" tabIndex={0}>
      <table {...props} />
    </div>
  ),
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
  img: ({ node: _node, alt }) => <span>{alt || "Image"}</span>,
};

export default function ChatMarkdown({ children }) {
  return (
    <div className="chat-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={components}>
        {String(children ?? "")}
      </ReactMarkdown>
    </div>
  );
}
