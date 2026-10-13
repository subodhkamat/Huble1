from pathlib import Path

from project_service import BASE_DIR


BRIDGE_START = "<!-- BUILDAI_RUNTIME_BRIDGE_START -->"
BRIDGE_END = "<!-- BUILDAI_RUNTIME_BRIDGE_END -->"

RUNTIME_BRIDGE = r"""
<!-- BUILDAI_RUNTIME_BRIDGE_START -->
<script>
(() => {
  if (window.__buildAIRuntimeBridgeInstalled) return;
  window.__buildAIRuntimeBridgeInstalled = true;

  function report(type, message, details = {}) {
    try {
      window.parent.postMessage(
        {
          source: "BUILDAI_RUNTIME_ERROR",
          type,
          message: String(message || "Unknown runtime error").slice(0, 4000),
          stack: String(details.stack || "").slice(0, 8000),
          filename: String(details.filename || "").slice(0, 2000),
          line: Number(details.line || 0),
          column: Number(details.column || 0),
          timestamp: Date.now()
        },
        "*"
      );
    } catch (_) {
      // Monitoring must never crash the generated application.
    }
  }

  window.addEventListener("error", (event) => {
    report("error", event.message || "Browser runtime error", {
      stack: event.error && event.error.stack,
      filename: event.filename,
      line: event.lineno,
      column: event.colno
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    report(
      "unhandledrejection",
      reason && reason.message ? reason.message : String(reason),
      { stack: reason && reason.stack }
    );
  });

  // React Error Boundaries can call this to report rendering failures.
  window.__buildAIReportError = (error, componentStack = "") => {
    report("react-error", error && error.message, {
      stack: [
        error && error.stack,
        componentStack
      ].filter(Boolean).join("\n")
    });
  };
})();
</script>
<!-- BUILDAI_RUNTIME_BRIDGE_END -->
"""


def install_runtime_bridge() -> None:
    """
    Add the browser error monitor to the generated project's index.html.
    Repeated calls replace the previous bridge rather than duplicating it.
    """
    root = Path(BASE_DIR).resolve()
    index_file = root / "index.html"

    if not index_file.is_file():
        raise FileNotFoundError(
            "Generated project index.html was not found. "
            "Generate a project before starting the preview."
        )

    content = index_file.read_text(encoding="utf-8")

    # Remove a previously installed bridge before inserting it again.
    start = content.find(BRIDGE_START)
    end = content.find(BRIDGE_END)

    if start != -1 and end != -1 and end >= start:
        end += len(BRIDGE_END)
        content = content[:start] + content[end:]

    head_end = content.lower().find("</head>")

    if head_end != -1:
        content = (
            content[:head_end]
            + RUNTIME_BRIDGE
            + "\n"
            + content[head_end:]
        )
    else:
        content = RUNTIME_BRIDGE + "\n" + content

    index_file.write_text(content, encoding="utf-8")