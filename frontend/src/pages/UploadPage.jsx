import { useMemo, useState } from "react";
import {
  analyzeFiles,
  getAnalysisProgress
} from "../services/api.js";

const PROGRESS_STEPS = [
  {
    label: "Upload files",
    minPercent: 0,
    messages: [
      "Preparing upload workspace",
      "Saving uploaded files",
      "Uploaded files saved"
    ]
  },
  {
    label: "Extract content",
    minPercent: 15,
    messages: [
      "Discovering files",
      "Files discovered",
      "Extracting document content",
      "Document content extracted"
    ]
  },
  {
    label: "Classify documents",
    minPercent: 51,
    messages: [
      "Classifying documents",
      "Documents classified"
    ]
  },
  {
    label: "Parse and reconcile",
    minPercent: 64,
    messages: [
      "Understanding notes",
      "Notes understood",
      "Parsing business entities",
      "Business entities parsed",
      "Reconciling note knowledge",
      "Building review items"
    ]
  },
  {
    label: "Generate report",
    minPercent: 94,
    messages: [
      "Generating report",
      "Saving report",
      "Report saved",
      "Report ready"
    ]
  }
];

export default function UploadPage({ onReport }) {
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(null);
  const [error, setError] = useState("");

  const fileCountLabel = useMemo(() => {
    if (files.length === 0) {
      return "No files selected";
    }

    return `${files.length} file${files.length === 1 ? "" : "s"} selected`;
  }, [files]);

  const progress = analysisProgress?.percent || 0;
  const progressSteps = buildProgressSteps(analysisProgress);
  const currentDetail = analysisProgress?.detail || "";

  function addFiles(fileList) {
    setError("");
    setFiles((currentFiles) => {
      const nextFiles = Array.from(fileList).filter(isSourceFile);

      return [
        ...currentFiles,
        ...nextFiles
      ];
    });
  }

  async function handleAnalyze() {
    if (files.length === 0) {
      setError("Select at least one file to analyze.");
      return;
    }

    setIsAnalyzing(true);
    const analysisId = createAnalysisId();
    let pollIntervalId = null;

    setAnalysisProgress({
      analysis_id: analysisId,
      status: "pending",
      percent: 1,
      message: "Preparing upload workspace",
      detail: "",
      events: [
        {
          message: "Preparing upload workspace",
          detail: ""
        }
      ]
    });
    setError("");

    try {
      pollIntervalId = window.setInterval(async () => {
        try {
          setAnalysisProgress(await getAnalysisProgress(analysisId));
        } catch {
          // The upload request may reach the server just after the first poll.
        }
      }, 2000);

      const reportId = await analyzeFiles(files, analysisId);
      const finalProgress = await getAnalysisProgress(analysisId);
      setAnalysisProgress(finalProgress);
      await onReport(reportId);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      if (pollIntervalId !== null) {
        window.clearInterval(pollIntervalId);
      }

      setIsAnalyzing(false);
    }
  }

  return (
    <section className="upload-panel">
      <div className="panel-heading">
        <div>
          <h1>Finance Record</h1>
          <p>Upload invoices, statements, receipts, and notes.</p>
        </div>
        <button
          className="primary-button"
          disabled={isAnalyzing || files.length === 0}
          onClick={handleAnalyze}
          type="button"
        >
          {isAnalyzing ? "Analyzing" : "Analyze"}
        </button>
      </div>

      {isAnalyzing ? (
        <section className="analysis-progress">
          <div className="progress-heading">
            <strong>Analysis in progress</strong>
            <span>{progress}%</span>
          </div>
          <div
            aria-label="Analysis progress"
            aria-valuemax="100"
            aria-valuemin="0"
            aria-valuenow={progress}
            className="progress-track"
            role="progressbar"
          >
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <ol className="analysis-log">
            {progressSteps.map((step) => (
              <li className={step.className} key={step.label}>
                <span>{step.label}</span>
              </li>
            ))}
          </ol>
          {currentDetail ? (
            <p className="analysis-current-detail">{currentDetail}</p>
          ) : null}
        </section>
      ) : null}

      <label
        className={`drop-zone ${isDragging ? "is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          addFiles(event.dataTransfer.files);
        }}
      >
        <input
          multiple
          onChange={(event) => addFiles(event.target.files)}
          type="file"
        />
        <span className="drop-title">Drop files here</span>
        <span className="drop-subtitle">or click to browse</span>
      </label>

      <div className="file-strip">
        <strong>{fileCountLabel}</strong>
        <div className="file-actions">
          <label className="secondary-button file-picker-button">
            Add Folder
            <input
              multiple
              onChange={(event) => addFiles(event.target.files)}
              type="file"
              webkitdirectory=""
            />
          </label>
          {files.length > 0 ? (
            <button
              className="secondary-button"
              onClick={() => setFiles([])}
              type="button"
            >
              Clear
            </button>
          ) : null}
        </div>
      </div>

      {files.length > 0 ? (
        <ul className="file-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <span>{file.webkitRelativePath || file.name}</span>
              <span>{formatBytes(file.size)}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}

function buildProgressSteps(analysisProgress) {
  const message = analysisProgress?.message || "";
  const percent = analysisProgress?.percent || 0;
  const activeIndex = PROGRESS_STEPS.findIndex((step) => (
    step.messages.includes(message)
  ));
  const fallbackActiveIndex = PROGRESS_STEPS.reduce(
    (currentIndex, step, index) => (
      percent >= step.minPercent ? index : currentIndex
    ),
    0
  );
  const currentIndex = activeIndex === -1 ? fallbackActiveIndex : activeIndex;

  return PROGRESS_STEPS.map((step, index) => {
    let className = "is-pending";

    if (index < currentIndex || percent === 100) {
      className = "is-complete";
    } else if (index === currentIndex) {
      className = "is-current";
    }

    return {
      ...step,
      className
    };
  });
}

function createAnalysisId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isSourceFile(file) {
  const path = file.webkitRelativePath || file.name;
  const filename = path.split("/").pop() || "";

  if (filename === ".DS_Store" || filename === "Thumbs.db") {
    return false;
  }

  return !filename.startsWith("~$");
}

function formatBytes(value) {
  if (!value) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(
    Math.floor(Math.log(value) / Math.log(1024)),
    units.length - 1
  );

  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
