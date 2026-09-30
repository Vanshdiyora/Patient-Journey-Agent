import { get } from "./client";

/** Action registry catalog (staff only). */
export const actionsApi = {
  registry: () => get("/api/v1/actions/registry"),
};
