import { get, post } from "./client";

/** Login, signup and identity endpoints. */
export const authApi = {
  login: (payload) => post("/api/v1/auth/login", payload),
  signup: (payload) => post("/api/v1/auth/signup", payload),
  me: () => get("/api/v1/users/me"),
};
