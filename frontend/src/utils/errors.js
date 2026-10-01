/**
 * API error extraction. Central so every surface reports failures identically.
 */

export function getErrorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") return detail;

  // FastAPI/Pydantic validation errors return an array of objects. Turn each
  // entry into readable text so React components never try to render objects.
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        const location = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== "body").join(" → ") : "";
        const message = item?.msg || "Invalid value";
        return location ? `${location}: ${message}` : message;
      })
      .join("; ");
  }

  if (detail && typeof detail === "object") {
    return detail.msg || detail.message || "The request was invalid.";
  }

  return error?.message || "Something went wrong.";
}
