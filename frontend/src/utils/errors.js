/**
 * API error extraction. Central so every surface reports failures identically.
 */

export function getErrorMessage(error) {
  return error?.response?.data?.detail || error?.message || "Something went wrong.";
}
