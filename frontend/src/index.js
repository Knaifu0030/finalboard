import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

/* Browser extensions (password managers, scrapers, AI sidebars) patch XMLHttpRequest and
   throw inside their own bundles. Those throws are not ours and must never be allowed to
   surface as an app error. Swallow anything whose stack lives in an extension. */
const EXTENSION_ORIGIN = /(chrome|moz|safari-web|ms-browser)-extension:\/\//;

const fromExtension = (parts) => {
  try {
    return EXTENSION_ORIGIN.test(parts.filter(Boolean).join(" "));
  } catch (e) {
    return false;
  }
};

window.addEventListener(
  "error",
  (event) => {
    if (fromExtension([event.filename, event.error && event.error.stack, event.message])) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  },
  true,
);

window.addEventListener(
  "unhandledrejection",
  (event) => {
    const r = event.reason;
    if (fromExtension([r && r.stack, r && r.message, typeof r === "string" ? r : null])) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  },
  true,
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
