import { get, post } from "./client";

/** Administrator-managed care pathway templates. */
export const pathwaysApi = {
  list: () => get("/api/v1/pathways"),
  create: (payload) => post("/api/v1/pathways", payload),
};
