import { useCallback, useState } from "react";

/**
 * useTabs — tiny state helper for tabbed panels. Keeps tab UI logic out of
 * pages so a tab bar is just: tabs config + active id + setActive.
 */
export function useTabs(initialTab) {
  const [active, setActive] = useState(initialTab);
  const select = useCallback((id) => setActive(id), []);
  return { active, select, isActive: (id) => active === id };
}
