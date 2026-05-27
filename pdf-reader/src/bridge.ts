import type { InMessage } from "./types";

const SOURCE = "pdf-reader";

export function sendMessage(msg: Record<string, unknown>) {
  window.parent.postMessage({ ...msg, source: SOURCE }, "*");
}

export function onMessage(callback: (msg: InMessage) => void) {
  const handler = (e: MessageEvent) => {
    if (e.data && typeof e.data === "object" && "type" in e.data) {
      callback(e.data as InMessage);
    }
  };
  window.addEventListener("message", handler);
  return () => window.removeEventListener("message", handler);
}

let pageTimer: ReturnType<typeof setTimeout> | null = null;
export function sendPageChanged(page: number) {
  if (pageTimer) clearTimeout(pageTimer);
  pageTimer = setTimeout(() => {
    sendMessage({ type: "PAGE_CHANGED", page });
  }, 300);
}
