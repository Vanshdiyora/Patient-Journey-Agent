import React from "react";
/**
 * JsonView â€” pretty-printed JSON block.
 */
export default function JsonView({ data, maxHeight }) {
  return (
    <pre className="json-view" style={maxHeight ? { maxHeight } : undefined}>
      {JSON.stringify(data ?? {}, null, 2)}
    </pre>
  );
}
