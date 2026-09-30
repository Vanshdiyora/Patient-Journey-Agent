import { get, post } from "./client";

/** Login and identity endpoints. */
export const authApi = {
  login: (payload) => post("/api/v1/auth/login", payload),
  me: () => get("/api/v1/users/me"),
};
