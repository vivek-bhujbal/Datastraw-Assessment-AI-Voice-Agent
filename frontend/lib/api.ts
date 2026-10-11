export const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/+$/, "");

export function socketUrl() {
  const url = new URL(apiUrl, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/$/, "")}/ws/call`;
  return url.toString();
}

