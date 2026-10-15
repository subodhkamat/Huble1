
import { useEffect, useRef, useState } from "react";
import "./App.css";
import { SpeedInsights } from "@vercel/speed-insights/next"

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

const examples = [
  "Build a student management dashboard",
  "Build a modern todo application",
  "Build a personal portfolio website",
];

export default function App() {
const [prompt, setPrompt] = useState("");
const [files, setFiles] = useState({});
const [selectedFile, setSelectedFile] = useState("");
const [loading, setLoading] = useState(false);
const [error, setError] = useState("");
const [message, setMessage] = useState("");
const [previewUrl, setPreviewUrl] = useState("");
const [previewLoading, setPreviewLoading] = useState(false);
const [previewError, setPreviewError] = useState("");
const [editPrompt, setEditPrompt] = useState("");
const [editing, setEditing] = useState(false);
const [debugging, setDebugging] = useState(false);
const [debugResult, setDebugResult] = useState(null);
const [runtimeError, setRuntimeError] = useState(null);
const [runtimeReportStatus, setRuntimeReportStatus] = useState("");
const [testing, setTesting] = useState(false);
const [testReport, setTestReport] = useState(null);
const [testError, setTestError] = useState("");

const [planningPrompt, setPlanningPrompt] = useState("");
const [projectPlan, setProjectPlan] = useState(null);
const [planning, setPlanning] = useState(false);
const [planningError, setPlanningError] = useState("");
const [terminalStatus, setTerminalStatus] = useState({
  running: false,
  logs: [],
});
const [terminalBusy, setTerminalBusy] = useState(false);
const [terminalError, setTerminalError] = useState("");


//refreshing token
async function refreshTerminalStatus() {
  try {
    const response = await fetch(`${API_URL}/terminal/status`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Unable to get terminal status.");
    }

    setTerminalStatus(data);
    return data;
  } catch (error) {
    setTerminalError(error.message || "Terminal status request failed.");
    return null;
  }
}

async function runTerminalAction(action) {
  setTerminalBusy(true);
  setTerminalError("");

  try {
    const response = await fetch(`${API_URL}/terminal/${action}`, {
      method: "POST",
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Terminal ${action} failed.`);
    }

    await refreshTerminalStatus();

    if (action === "start" && data.preview_url) {
      setPreviewUrl(data.preview_url);
    }

    if (action === "stop") {
      setTerminalStatus((current) => ({
        ...current,
        running: false,
        pid: null,
        preview_url: null,
      }));
    }

    return data;
  } catch (error) {
    setTerminalError(error.message || "Terminal action failed.");
    await refreshTerminalStatus();
    return null;
  } finally {
    setTerminalBusy(false);
  }
}


//project planning

async function createProjectPlan() {
  if (planningPrompt.trim().length < 3) {
    setPlanningError("Describe the feature you want to build.");
    return;
  }

  setPlanning(true);
  setPlanningError("");
  setProjectPlan(null);

  try {
    const response = await fetch(`${API_URL}/plan-project`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt: planningPrompt.trim(),
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to create the project plan."
      );
    }

    setProjectPlan(data.plan);
  } catch (error) {
    setPlanningError(
      error instanceof Error
        ? error.message
        : "An unexpected planning error occurred."
    );
  } finally {
    setPlanning(false);
  }
}

//project testing

async function runProjectTests() {
  setTesting(true);
  setTestError("");
  setTestReport(null);

  try {
    const response = await fetch(`${API_URL}/test-project`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preview_url: previewUrl || null,
        run_browser: true,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || data.message || "Testing request failed."
      );
    }

    setTestReport(data);
  } catch (error) {
    setTestError(
      error instanceof Error
        ? error.message
        : "An unexpected testing error occurred."
    );
  } finally {
    setTesting(false);
  }
}

//fix run time
async function fixRuntimeError() {
  if (!runtimeError) return;

  setError("");
  setMessage("");
  setRuntimeReportStatus("AI is analyzing the runtime error...");

  try {
    const prompt = `
Fix this runtime error in the current generated React project.

Error type: ${runtimeError.type}
Error message: ${runtimeError.message}
Source file: ${runtimeError.filename || "Unknown"}
Line: ${runtimeError.line}
Column: ${runtimeError.column}

Stack trace:
${runtimeError.stack || "No stack trace available."}

Instructions:
- Identify the most likely root cause.
- Inspect the current project files before editing.
- Fix only the files necessary to resolve this error.
- Preserve the existing design and functionality.
- Return complete updated file contents through the existing edit API.
- Do not invent a successful result; the fix must still be tested.
`;

    const response = await fetch(`${API_URL}/edit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "AI could not repair the runtime error."
      );
    }

    if (!data.success) {
      throw new Error(data.summary || "The AI repair was unsuccessful.");
    }

    if (data.files && typeof data.files === "object") {
      setFiles((previous) => ({
        ...previous,
        ...data.files,
      }));
    }

    if (data.changed_files?.length > 0) {
      setSelectedFile(data.changed_files[0]);
    }

    setRuntimeReportStatus(
      data.summary || "AI applied a proposed runtime fix."
    );

    // Refresh the preview so Vite can reload the updated project.
    if (previewUrl) {
      const separator = previewUrl.includes("?") ? "&" : "?";

      setPreviewUrl(
        `${previewUrl}${separator}refresh=${Date.now()}`
      );
    }

    setMessage(
      "AI applied a runtime-error fix. Test the affected feature and run Auto-fix build errors to validate the production build."
    );
  } catch (err) {
    setError(err.message || "Could not fix the runtime error.");
    setRuntimeReportStatus("AI repair failed.");
  }
}

const previewFrameRef = useRef(null);
// runtime
useEffect(() => {
  function handleRuntimeMessage(event) {
    // Only accept messages from our own preview iframe.
    if (event.source !== previewFrameRef.current?.contentWindow) {
      return;
    }

    // Require the expected message format.
    if (
      !event.data ||
      event.data.source !== "BUILDAI_RUNTIME_ERROR"
    ) {
      return;
    }

    const report = {
      type: String(event.data.type || "error").slice(0, 100),
      message: String(event.data.message || "Unknown runtime error").slice(0, 4000),
      stack: String(event.data.stack || "").slice(0, 8000),
      filename: String(event.data.filename || "").slice(0, 2000),
      line: Math.max(0, Number(event.data.line) || 0),
      column: Math.max(0, Number(event.data.column) || 0),
      timestamp: Number(event.data.timestamp) || Date.now(),
    };

    setRuntimeError(report);
    setRuntimeReportStatus("Sending error report...");

    fetch(`${API_URL}/runtime-error`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(report),
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("The backend rejected the error report.");
        }

        setRuntimeReportStatus("Error reported to backend.");
      })
      .catch(() => {
        setRuntimeReportStatus(
          "Error detected, but the backend report failed."
        );
      });
  }

  window.addEventListener("message", handleRuntimeMessage);

  return () => {
    window.removeEventListener("message", handleRuntimeMessage);
  };
}, []);


async function runAutoDebug() {
  setDebugging(true);
  setError("");
  setMessage("");
  setDebugResult(null);

  try {
    const response = await fetch(`${API_URL}/auto-debug`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        max_attempts: 3,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Auto-debug request failed."
      );
    }

    // Synchronize the code viewer with AI-modified files.
    if (data.files && typeof data.files === "object") {
      setFiles((previous) => ({
        ...previous,
        ...data.files,
      }));

      const changed = data.changed_files || [];

      if (changed.length > 0) {
        setSelectedFile(changed[0]);
      }
    }

    setDebugResult(data);

    if (data.success) {
      setMessage(
        `${data.summary} Build attempts: ${data.attempts}.`
      );

      // Reload the iframe URL after successful debugging.
      if (previewUrl) {
        const separator = previewUrl.includes("?") ? "&" : "?";

        setPreviewUrl(
          `${previewUrl}${separator}refresh=${Date.now()}`
        );
      }
    } else {
      setError(
        `${data.summary} Review the build output below for details.`
      );
    }
  } catch (err) {
    setError(err.message || "Auto-debug failed.");
  } finally {
    setDebugging(false);
  }
}


async function editExistingProject() {
  if (editPrompt.trim().length < 3) {
    setError("Describe the change you want to make.");
    return;
  }

  setEditing(true);
  setError("");
  setMessage("");

  try {
    const response = await fetch(`${API_URL}/edit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt: editPrompt,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Project editing failed."
      );
    }

    setFiles((previous) => ({
      ...previous,
      ...data.files,
    }));

    if (data.changed_files?.length > 0) {
      setSelectedFile(data.changed_files[0]);

      // Reload the preview if it is already open.
      setPreviewUrl((url) =>
        url
          ? `${url.split("?")[0]}?refresh=${Date.now()}`
          : ""
      );
    }

    setMessage(
      data.changed_files?.length
        ? `${data.summary} Updated: ${data.changed_files.join(", ")}`
        : data.summary
    );

    setEditPrompt("");
  } catch (err) {
    setError(
      err.message || "Could not edit the project."
    );
  } finally {
    setEditing(false);
  }
}


async function downloadProject() {
  setError("");
  setMessage("Preparing project ZIP...");

  try {
    const response = await fetch(
      `${API_URL}/download`
    );

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));

      throw new Error(
        data.detail || "Failed to download project."
      );
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "generated_project.zip";

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);

    setMessage("Project ZIP downloaded.");
  } catch (err) {
    setError(
      err.message || "Project download failed."
    );
    setMessage("");
  }
}

async function startLivePreview() {
  setPreviewLoading(true);
  setPreviewError("");

  try {
    const response = await fetch(
      `${API_URL}/preview`,
      {
        method: "POST",
      }
    );

    const data = await response.json(); 
    console.log(data)
    if (!response.ok) {
      throw new Error(
        data.detail || "Could not start preview."
      );
    }

    setPreviewUrl(data.preview_url);
    console.log(previewUrl)
  } catch (err) {
    setPreviewError(
      err.message || "Preview failed."
    );
  } finally {
    setPreviewLoading(false);
  }
}



  async function generateProject() {
    if (prompt.trim().length < 5) {
      setError("Please describe your application.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    setFiles({});
    setSelectedFile("");

    try {
      const response = await fetch(
        `${API_URL}/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ prompt }),
        }
      );
      console.log(response)

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Generation failed."
        );
      }

      setFiles(data.files);
      setSelectedFile(
        Object.keys(data.files)[0] || ""
      );
      setMessage(data.message);
    } catch (err) {
      setError(
        err.message ||
          "Cannot connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  function downloadFile() {
    if (!selectedFile || !files[selectedFile]) {
      return;
    }

    const blob = new Blob(
      [files[selectedFile]],
      { type: "text/plain;charset=utf-8" }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = selectedFile.split("/").pop();
    link.click();

    URL.revokeObjectURL(url);
  }

  return (
    <main className="app">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-icon">✳</span>
          BuildAI
        </a>
        <span className="status">
          <span className="status-dot" />
          AI workspace
        </span>
      </header>

      <section className="hero">
        <span className="eyebrow">
          YOUR IDEA, YOUR APPLICATION
        </span>

        <h1>
          Build something
          <br />
          <span>extraordinary.</span>
        </h1>

        <p className="subtitle">
          Describe your idea. Let AI turn it into
          a React project with real source files.
        </p>

        <div className="prompt-box">
          <textarea
            value={prompt}
            onChange={(event) =>
              setPrompt(event.target.value)
            }
            placeholder="Build a modern dashboard with login, analytics, charts and a sidebar..."
            rows={4}
            maxLength={5000}
          />

          <div className="prompt-footer">
            <span className="hint">
              React · Vite · AI generation
            </span>

            <button
              onClick={generateProject}
              disabled={loading}
            >
              {loading
                ? "Generating..."
                : "✦ Generate project"}
            </button>
          </div>
        </div>

        <div className="examples">
          <span>Try an idea:</span>
          {examples.map((example) => (
            <button
              className="example"
              key={example}
              onClick={() => setPrompt(example)}
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      {loading && (
        <p className="notice">
          AI is generating your project. This may
          take a little while...
        </p>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}


      {Object.keys(files).length > 0 && (
        <>
          {/* Modify Existing Project */}
     

          {/* Generated Project Workspace */}
          <section className="workspace">
                 

            <div className="workspace-header">
              <div>
                <h2>Your generated project</h2>
                <p>
                  {Object.keys(files).length} files generated
                </p>
              </div>

              <div className="workspace-actions">
                <button
                  className="secondary-button"
                  onClick={downloadFile}
                  disabled={!selectedFile}
                >
                  Download selected file
                </button>

                <button
                  className="preview-button"
                  onClick={downloadProject}
                  disabled={Object.keys(files).length === 0}
                >
                  ↓ Download full project
                </button>

                <button
                  className="preview-button"
                  onClick={startLivePreview}
                  disabled={previewLoading}
                >
                  {previewLoading
                    ? "Starting preview..."
                    : "▶ Run preview"}
                </button>

                <button
                  className="debug-button"
                  onClick={runAutoDebug}
                  disabled={debugging || loading}
                >
  {debugging ? "AI is fixing errors..." : "🛠 Auto-fix build errors"}
</button>

<button
  type="button"
  className="secondary-button"
  onClick={runProjectTests}
  disabled={testing}
>
  {testing ? "Testing project..." : "Run Tests"}
</button>
              </div>
            </div>

            {/* Preview Error */}
            {previewError && (
              <p className="error" role="alert">
                {previewError}
              </p>
            )}

            {/* File Explorer and Code Editor */}
            <div className="editor">
              <aside className="file-list">
                <div className="file-heading">
                  PROJECT FILES
                </div>

                {Object.keys(files).map((file) => (
                  <button
                    key={file}
                    className={
                      selectedFile === file
                        ? "file active"
                        : "file"
                    }
                    onClick={() => setSelectedFile(file)}
                  >
                    <span>▤</span>
                    {file}
                  </button>
                ))}
              </aside>

              <div className="code-panel">
                <div className="code-heading">
                  <span>{selectedFile || "Select a file"}</span>
                  <span>Source</span>
                </div>

                <pre>
                  <code>
                    {selectedFile
                      ? files[selectedFile] || ""
                      : "Select a file to view its source code."}
                  </code>
                </pre>
              </div>
            </div>

            {/* Live Application Preview */}
            {previewUrl && (
              <section className="preview-section">
                <div className="preview-heading">
                  <div>
                    <h2>Live preview</h2>
                    <p>
                      Your generated application is running.
                    </p>
                  </div>

                  <button
                    className="secondary-button"
                    onClick={() => {
                      const separator = previewUrl.includes("?")
                        ? "&"
                        : "?";

                      setPreviewUrl(
                        `${previewUrl}${separator}refresh=${Date.now()}`
                      );
                    }}
                  >
                    Refresh preview
                  </button>
                </div>
  {/** plaining */}
   



              <iframe
  ref={previewFrameRef}
  className="preview-frame"
  src={previewUrl}
  title="Generated application preview"
  sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-popups"
/>
{testError && (
  <section className="test-report">
    <h3>Testing request failed</h3>
    <p>{testError}</p>
  </section>
)}

{testReport && (
  <section className="test-report">
    <div className="test-report-heading">
      <div>
        <h2>Autonomous Test Report</h2>
        <p>{testReport.message}</p>
      </div>

      <span>
        {testReport.summary.passed} passed /{" "}
        {testReport.summary.failed} failed
      </span>
    </div>

    <div className="test-summary">
      <div>
        <strong>{testReport.summary.passed}</strong>
        <span>Passed</span>
      </div>

      <div>
        <strong>{testReport.summary.failed}</strong>
        <span>Failed</span>
      </div>

      <div>
        <strong>{testReport.summary.skipped}</strong>
        <span>Skipped</span>
      </div>
    </div>

    <div className="test-results">
      {testReport.tests.map((test, index) => (
        <article
          className="test-result"
          key={`${test.name}-${index}`}
        >
          <div>
            <strong>{test.name}</strong>
            <p>{test.message}</p>
          </div>

          <span className={`test-status ${test.status}`}>
            {test.status.toUpperCase()}
          </span>
        </article>
      ))}
    </div>

    {testReport.build_output && (
      <details>
        <summary>View build logs</summary>
        <pre>{testReport.build_output}</pre>
      </details>
    )}
  </section>
)}

{runtimeError && (
  <section className="runtime-error-panel">
    <div className="runtime-error-heading">
      <div>
        <h3>Browser runtime error detected</h3>
        <p>{runtimeReportStatus}</p>
      </div>

      <button
        className="debug-button"
        onClick={fixRuntimeError}
      >
        🛠 Fix with AI
      </button>
    </div>

    <p className="runtime-error-message">
      {runtimeError.message}
    </p>

    {runtimeError.filename && (
      <p className="runtime-error-location">
        {runtimeError.filename}
        {runtimeError.line > 0 && `:${runtimeError.line}`}
        {runtimeError.column > 0 && `:${runtimeError.column}`}
      </p>
    )}

    {runtimeError.stack && (
      <details>
        <summary>View stack trace</summary>
        <pre className="debug-output">
          {runtimeError.stack}
        </pre>
      </details>
    )}

    <button
      className="secondary-button"
      onClick={() => {
        setRuntimeError(null);
        setRuntimeReportStatus("");
      }}
    >
      Dismiss error
    </button>
  </section>
)}

              </section>
            )}
          </section>

          
        </>
      )}

      <footer>
        Built with React, FastAPI and AI
      </footer>
    </main>
  );
}
