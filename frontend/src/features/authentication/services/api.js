import { get, post } from "../../../services/client";

export const authApi = {
  login: (payload) => post("/api/v1/auth/login", payload),
  changePassword: (payload) => post("/api/v1/auth/change-password", payload),
  me: () => get("/api/v1/users/me"),
};
