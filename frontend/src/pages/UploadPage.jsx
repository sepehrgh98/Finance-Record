import { useEffect, useMemo, useState } from "react";
import { analyzeFiles } from "../services/api.js";

const ANALYSIS_STAGES = [
  "Preparing upload workspace",
  "Detecting document formats",
  "Extracting document content",
  "Classifying documents",
  "Parsing invoices, statements, and receipts",
  "Understanding notes",
  "Reconciling linked notes",
  "Generating report"
];

export default function UploadPage({ onReport }) {
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);
  const [error, setError] = useState("");

  const fileCountLabel = useMemo(() => {
    if (files.length === 0) {
      return "No files selected";
    }

    return `${files.length} file${files.length === 1 ? "" : "s"} selected`;
  }, [files]);

  const progress = isAnalyzing
    ? Math.min(
        96,
        Math.round(((analysisStep + 1) / ANALYSIS_STAGES.length) * 100)
      )
    : 0;

  useEffect(() => {
    if (!isAnalyzing) {
      return undefined;
    }

    setAnalysisStep(0);

    const intervalId = window.setInterval(() => {
      setAnalysisStep((currentStep) => {
        if (currentStep >= ANALYSIS_STAGES.length - 1) {
          return currentStep;
        }

        return currentStep + 1;
      });
    }, 1400);

    return () => window.clearInterval(intervalId);
  }, [isAnalyzing]);

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
    setAnalysisStep(0);
    setError("");

    try {
      const reportId = await analyzeFiles(files);
      setAnalysisStep(ANALYSIS_STAGES.length - 1);
      await onReport(reportId);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsAnalyzing(false);
    }
  }

  return (
    <section className="upload-panel">
      <div className="panel-heading">
        <div>
          <h1>Document Intelligence</h1>
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
            {ANALYSIS_STAGES.slice(0, analysisStep + 1).map((stage, index) => (
              <li key={stage}>
                <span className={index === analysisStep ? "is-current" : ""}>
                  {stage}
                </span>
              </li>
            ))}
          </ol>
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
