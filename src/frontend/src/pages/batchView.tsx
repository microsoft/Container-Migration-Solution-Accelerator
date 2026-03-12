import * as React from "react"
import { useParams } from "react-router-dom"
import { useNavigate } from "react-router-dom"
import { useState, useEffect } from "react"
import Content from "../components/Content/Content";
import Header from "../components/Header/Header";
import HeaderTools from "../components/Header/HeaderTools";
import PanelLeft from "../components/Panels/PanelLeft";
import apiService from '../services/ApiService';
import {
  Button,
  Text,
  Card,
  tokens,
  Spinner,
  Tooltip,
} from "@fluentui/react-components"
import {
  DismissCircle24Regular,
  CheckmarkCircle24Regular,
  DocumentRegular,
  ArrowDownload24Regular,
  bundleIcon,
  HistoryFilled,
  HistoryRegular,
  Warning24Regular
} from "@fluentui/react-icons"
import { Light as SyntaxHighlighter } from "react-syntax-highlighter"
import sql from "react-syntax-highlighter/dist/esm/languages/hljs/sql"
import yaml from "react-syntax-highlighter/dist/esm/languages/hljs/yaml"
import markdown from "react-syntax-highlighter/dist/esm/languages/hljs/markdown"
import json from "react-syntax-highlighter/dist/esm/languages/hljs/json"
import { vs } from "react-syntax-highlighter/dist/esm/styles/hljs"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeRaw from "rehype-raw"
import mermaid from "mermaid"
import PanelRight from "../components/Panels/PanelRight";
import PanelRightToolbar from "../components/Panels/PanelRightToolbar";
import BatchHistoryPanel from "../components/batchHistoryPanel";
import ConfirmationDialog from "../commonComponents/ConfirmationDialog/confirmationDialogue";
import { determineFileStatus, filesLogsBuilder, renderErrorSection, useStyles, renderFileError, filesErrorCounter, completedFiles, hasFiles, fileErrorCounter, BatchSummary, fileWarningCounter } from "../api/utils";
export const History = bundleIcon(HistoryFilled, HistoryRegular);
import { format } from "sql-formatter";


SyntaxHighlighter.registerLanguage("sql", sql)
SyntaxHighlighter.registerLanguage("yaml", yaml)
SyntaxHighlighter.registerLanguage("markdown", markdown)
SyntaxHighlighter.registerLanguage("json", json)



interface FileItem {
  id: string;
  name: string;
  type: "summary" | "code";
  status: string;
  code?: string;
  translatedCode?: string;
  file_logs?: any[];
  errorCount?: number;
  warningCount?: number;
}

// Initialize mermaid for diagram rendering
mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });

// Mermaid code block renderer
const MermaidBlock: React.FC<{ chart: string }> = ({ chart }) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [svg, setSvg] = React.useState<string>('');

  React.useEffect(() => {
    const renderChart = async () => {
      try {
        const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
        const { svg: renderedSvg } = await mermaid.render(id, chart);
        setSvg(renderedSvg);
      } catch (err) {
        console.warn('Mermaid render failed:', err);
        setSvg(`<pre style="color:#888">${chart}</pre>`);
      }
    };
    renderChart();
  }, [chart]);

  return (
    <div
      ref={containerRef}
      dangerouslySetInnerHTML={{ __html: svg }}
      style={{ textAlign: 'center', margin: '16px 0', overflow: 'auto' }}
    />
  );
};

// GitHub-style markdown table and content styles
const markdownStyles = `
  .gh-markdown table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 14px;
  }
  .gh-markdown th, .gh-markdown td {
    border: 1px solid #d0d7de;
    padding: 8px 12px;
    text-align: left;
  }
  .gh-markdown th {
    background-color: #f6f8fa;
    font-weight: 600;
  }
  .gh-markdown tr:nth-child(even) {
    background-color: #f6f8fa;
  }
  .gh-markdown h1, .gh-markdown h2 {
    border-bottom: 1px solid #d0d7de;
    padding-bottom: 8px;
    margin-top: 24px;
  }
  .gh-markdown h3, .gh-markdown h4 {
    margin-top: 20px;
  }
  .gh-markdown code {
    background-color: #eff1f3;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
  }
  .gh-markdown pre {
    background-color: #f6f8fa;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
  }
  .gh-markdown pre code {
    background-color: transparent;
    padding: 0;
  }
  .gh-markdown blockquote {
    border-left: 4px solid #d0d7de;
    padding: 0 16px;
    color: #656d76;
    margin: 16px 0;
  }
  .gh-markdown ul, .gh-markdown ol {
    padding-left: 24px;
  }
  .gh-markdown li {
    margin: 4px 0;
  }
  .gh-markdown a {
    color: #0969da;
    text-decoration: none;
  }
  .gh-markdown a:hover {
    text-decoration: underline;
  }
  .gh-markdown hr {
    border: none;
    border-top: 1px solid #d0d7de;
    margin: 24px 0;
  }
`;

const BatchStoryPage = () => {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const [showLeaveDialog, setShowLeaveDialog] = useState(false);
  const styles = useStyles();
  const [batchTitle, setBatchTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [fileLoading, setFileLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [uploadId, setUploadId] = useState<string>("");
  const [isPanelOpen, setIsPanelOpen] = React.useState(false);

  // Files state with a summary file
  const [files, setFiles] = useState<FileItem[]>([]);

  const [selectedFileId, setSelectedFileId] = useState<string>("");
  const [expandedSections, setExpandedSections] = useState(["errors"]);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string>("");
  const [selectedFileTranslatedContent, setSelectedFileTranslatedContent] = useState<string>("");
  const [telemetryData, setTelemetryData] = useState<any>(null);

  // Helper function to determine file type and language for syntax highlighting
  const getFileLanguageAndType = (fileName: string) => {
    const extension = fileName.toLowerCase().split('.').pop();
    switch (extension) {
      case 'sql':
        return { language: 'sql', type: 'SQL' };
      case 'yaml':
      case 'yml':
        return { language: 'yaml', type: 'YAML' };
      case 'md':
      case 'markdown':
        return { language: 'markdown', type: 'Markdown' };
      case 'json':
        return { language: 'json', type: 'JSON' };
      default:
        return { language: 'sql', type: 'T-SQL' }; // Default to SQL for backwards compatibility
    }
  };

  // Helper function to format content based on file type
  const formatContent = (content: string, fileName: string) => {
    const { language } = getFileLanguageAndType(fileName);

    // Only apply SQL formatting for SQL files
    if (language === 'sql') {
      try {
        return format(content, { language: "tsql" });
      } catch (error) {
        console.warn("SQL formatting failed, returning original content:", error);
        return content;
      }
    }

    // Return content as-is for YAML and Markdown files
    return content;
  };


  // Fetch batch data from API
  useEffect(() => {
    if (!batchId || !(batchId.length === 36)) {
      setError("Invalid batch ID provided");
      setLoading(false);
      return;
    }

    const fetchBatchData = async () => {
      try {
        setLoading(true);
        setDataLoaded(false);

        const responseData = await apiService.get(`/process/process-summary/${batchId}`);

        // Handle the new response format
        if (!responseData || !responseData.files) {
          throw new Error("Invalid data format received from server");
        }

        // Adapt the new response format to match our expected BatchSummary format
        const data: BatchSummary = {
          batch_id: responseData.Process.process_id,
          upload_id: responseData.Process.process_id, // Use process_id for downloads
          date_created: responseData.Process.created_at,
          total_files: responseData.Process.file_count,
          status: "completed", // All files are completed
          completed_files: responseData.files.length, // All files are completed
          error_count: 0, // No errors in simplified version
          warning_count: 0, // No warnings in simplified version
          hasFiles: responseData.files.length,
          files: responseData.files.map(file => ({
            file_id: file.filename, // Use filename as file_id
            name: file.filename, // Use filename for display
            status: "completed", // All files are completed
            file_result: null,
            error_count: 0,
            warning_count: 0,
            file_logs: [],
          }))
        };

        setBatchSummary(data);
        setUploadId(data.upload_id);

        // Set batch title with completed file count only
        setBatchTitle(
          `Completed (${data.total_files})`
        );


        // Create file list from API response
        const fileItems: FileItem[] = data.files.map(file => ({
          id: file.file_id, // This is now the filename
          name: file.name, // This is now the filename
          type: "code",
          status: "completed", // All files are completed
          code: "", // Don't store content here, will fetch on demand
          translatedCode: "", // Don't store content here, will fetch on demand
          errorCount: 0,
          file_logs: [],
          warningCount: 0
        }));

        // Add summary file
        const updatedFiles: FileItem[] = [
          {
            id: "summary",
            name: "Summary",
            type: "summary",
            status: "completed",
            errorCount: 0, // No errors in simplified version
            warningCount: 0, // No warnings in simplified version
            file_logs: []
          },
          ...fileItems
        ];

        setFiles(updatedFiles as FileItem[]);
        setSelectedFileId("summary"); // Default to summary view
        setDataLoaded(true);
        setLoading(false);

        // Fetch telemetry data for the summary page
        try {
          const telemetry = await apiService.get(`/process/status/${batchId}/render/`);
          if (telemetry) {
            setTelemetryData(telemetry);
          }
        } catch (telErr) {
          console.warn("Could not load telemetry data:", telErr);
        }
      } catch (err) {
        console.error("Error fetching batch data:", err);
        setError(err instanceof Error ? err.message : "An unknown error occurred");
        setLoading(false);
      }
    };

    fetchBatchData();
  }, [batchId]);

  // Fetch file content when a file is selected
  useEffect(() => {
    if (selectedFileId === "summary" || !selectedFileId || fileLoading) {
      return;
    }

    const fetchFileContent = async () => {
      try {
        setFileLoading(true);
        const data = await apiService.get(`/process/${batchId}/file/${encodeURIComponent(selectedFileId)}`);

        if (data) {
          setSelectedFileContent(data.content || "");
          setSelectedFileTranslatedContent(data.content || ""); // Use content for both since we only have one version
        }

        setFileLoading(false);
      } catch (err) {
        console.error("Error fetching file content:", err);
        setFileLoading(false);
      }
    };

    fetchFileContent();
  }, [selectedFileId]);


  const renderWarningContent = () => {
    if (!expandedSections.includes("warnings")) return null;

    if (!batchSummary) return null;

    // Group warnings by file
    const warningFiles = files.filter(file => file.warningCount && file.warningCount > 0 && file.id !== "summary");

    if (warningFiles.length === 0) {
      return (
        <div className={styles.errorItem}>
          <Text>No warnings found.</Text>
        </div>
      );
    }

    return (
      <div>
        {warningFiles.map((file, fileIndex) => (
          <div key={fileIndex} className={styles.errorItem}>
            <div className={styles.errorTitle}>
              <Text weight="semibold">{file.name} ({file.warningCount})</Text>
              <Text className={styles.errorSource}>source</Text>
            </div>
            <div className={styles.errorDetails}>
              <Text>Warning in file processing. See file for details.</Text>
            </div>
          </div>
        ))}
      </div>
    );
  };

  // Helper function to count JSON/YAML files
  const getJsonYamlFileCount = () => {
    return files.filter(file => {
      if (file.id === "summary") return false;
      const extension = file.name.toLowerCase().split('.').pop();
      return extension === 'json' || extension === 'yaml' || extension === 'yml';
    }).length;
  };

  // Helper function to count .md files (reports)
  const getMdFileCount = () => {
    return files.filter(file => {
      if (file.id === "summary") return false;
      const extension = file.name.toLowerCase().split('.').pop();
      return extension === 'md';
    }).length;
  };

  const renderContent = () => {
    // Define header content based on selected file
    const renderHeader = () => {
      const selectedFile = files.find((f) => f.id === selectedFileId);

      if (!selectedFile) return null;

      const title = selectedFile.id === "summary" ? "Summary" : getFileLanguageAndType(selectedFile.name).type;

      return (
        <div className={styles.summaryHeader}
          style={{
            width: isPanelOpen ? "calc(102% - 340px)" : "96%",
            transition: "width 0.3s ease-in-out",
          }}
        >
          <Text size={500} weight="semibold">{title}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, paddingRight: "20px" }}>
            AI-generated content may be incorrect
          </Text>
        </div>
      );
    };

    if (loading) {
      return (
        <>
          {renderHeader()}
          <div className={styles.loadingContainer}>
            <Spinner size="large" />
            <Text size={500}>Loading batch data...</Text>
          </div>
        </>
      );
    }

    if (error) {
      return (
        <>
          {renderHeader()}
          <div className={styles.loadingContainer}>
            <Text size={500} style={{ color: tokens.colorStatusDangerForeground1 }}>
              Error: {error}
            </Text>
            <Button appearance="primary" onClick={() => navigate("/")}>
              Return to Home
            </Button>
          </div>
        </>
      );
    }

    if (!dataLoaded || !batchSummary) {
      return (
        <>
          {renderHeader()}
          <div className={styles.loadingContainer}>
            <Text size={500}>No data available</Text>
            <Button appearance="primary" onClick={() => navigate("/")}>
              Return to Home
            </Button>
          </div>
        </>
      );
    }

    const selectedFile = files.find((f) => f.id === selectedFileId);

    if (!selectedFile) {
      return (
        <>
          {renderHeader()}
          <div className={styles.loadingContainer}>
            <Text size={500}>No file selected</Text>
          </div>
        </>
      );
    }

    // If a specific file is selected (not summary), show the file content
    if (selectedFile.id !== "summary") {
      return (
        <>
          {renderHeader()}
          <Card className={styles.codeCard}
            style={{
              width: isPanelOpen ? "calc(100% - 320px)" : "98%",
              transition: "width 0.3s ease-in-out",
            }}>
            {getFileLanguageAndType(selectedFile.name).language !== 'markdown' && (
            <div className={styles.codeHeader}>
              <Text weight="semibold">
                {selectedFile.name} {selectedFileTranslatedContent ? "(Migrated)" : ""}
              </Text>
            </div>
            )}
            {fileLoading ? (
              <div style={{ padding: "20px", textAlign: "center" }}>
                <Spinner />
                <Text>Loading file content...</Text>
              </div>
            ) : (
              <>
                {!selectedFile.errorCount && selectedFile.warningCount ? (
                  <>
                    <Card className={styles.warningContent}>
                      <Text weight="semibold">File processed with warnings</Text>
                    </Card>
                    <Text style={{ padding: "20px" }}>
                      {renderFileError(selectedFile)}
                    </Text>
                  </>
                ) : null}
                {selectedFileTranslatedContent ? (
                  getFileLanguageAndType(selectedFile.name).language === 'markdown' ? (
                    <div className="gh-markdown" style={{
                      margin: 0,
                      padding: "16px 24px",
                      backgroundColor: tokens.colorNeutralBackground1,
                      borderRadius: "4px",
                      overflow: "auto",
                      maxHeight: "70vh",
                      lineHeight: "1.6",
                      fontSize: "14px",
                    }}>
                      <style>{markdownStyles}</style>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeRaw]}
                        components={{
                          code({ className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '');
                            const codeText = String(children).replace(/\n$/, '');
                            if (match && match[1] === 'mermaid') {
                              return <MermaidBlock chart={codeText} />;
                            }
                            // Inline code vs block code
                            if (!className) {
                              return <code {...props}>{children}</code>;
                            }
                            return (
                              <SyntaxHighlighter
                                language={match ? match[1] : 'text'}
                                style={vs}
                                customStyle={{ margin: 0, borderRadius: '6px' }}
                              >
                                {codeText}
                              </SyntaxHighlighter>
                            );
                          }
                        }}
                      >
                        {selectedFileTranslatedContent}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <SyntaxHighlighter
                      language={getFileLanguageAndType(selectedFile.name).language}
                      style={vs}
                      showLineNumbers
                      customStyle={{
                        margin: 0,
                        padding: "16px",
                        backgroundColor: tokens.colorNeutralBackground1,
                      }}
                    >
                      {formatContent(selectedFileTranslatedContent, selectedFile.name)}
                    </SyntaxHighlighter>
                  )
                ) : (
                  <>
                    <Card className={styles.errorContent}>
                      <Text weight="semibold">Unable to process the file</Text>
                    </Card>
                    <Text style={{ padding: "20px" }}>
                      {renderFileError(selectedFile)}
                    </Text>
                  </>
                )}
              </>
            )}
          </Card>
        </>
      );
    }

    // Show the summary page when summary is selected
    if (selectedFile.id === "summary" && batchSummary) {
      // Check if there are no errors and all JSON/YAML files are processed successfully
      const noErrors = (batchSummary.error_count === 0);
      const jsonYamlFileCount = getJsonYamlFileCount();
      const allJsonYamlFilesProcessed = (jsonYamlFileCount >= 0); // All existing JSON/YAML files are considered processed
      if (noErrors && allJsonYamlFilesProcessed) {
        // Show the success message UI with the green banner and checkmark
        return (
          <>
            {renderHeader()}
            <div className={styles.summaryContent}
              style={{
                width: isPanelOpen ? "calc(100% - 340px)" : "96%",
                transition: "width 0.3s ease-in-out",
                overflowX: "hidden",
              }}>
              {/* Green success banner */}
              <Card className={styles.summaryCard}>
                <div style={{ padding: "8px" }}>
                  <Text weight="semibold">
                    {getJsonYamlFileCount()} {getJsonYamlFileCount() === 1 ? 'file' : 'files'} processed successfully and {getMdFileCount()} {getMdFileCount() === 1 ? 'report' : 'reports'} generated successfully.
                  </Text>
                </div>
              </Card>

              {/* Success checkmark and message */}
              <div className="file-content"
                style={{
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginTop: '24px',
                  width: "100%",
                  maxWidth: "800px",
                  margin: "auto",
                  transition: "width 0.3s ease-in-out",
                }}>
                <img
                  src={getJsonYamlFileCount() === 0 ? "/images/Crossmark.png" : "/images/Checkmark.png"}
                  alt={getJsonYamlFileCount() === 0 ? "No files" : "Success checkmark"}
                  style={{ width: '80px', height: '80px', marginBottom: '12px', marginTop: '24px' }}
                />
                <Text size={600} weight="semibold" style={{ marginBottom: '8px' }}>
                  {getJsonYamlFileCount() === 0 ? "No files to process!" : "No errors! Your files are ready to download."}
                </Text>
                <Text style={{ marginBottom: '16px', color: '#666' }}>
                  {getJsonYamlFileCount() === 0
                    ? "No files were found in this migration batch. Please upload files to proceed with the migration process."
                    : "Your files have been successfully migrated with no errors. All files are now ready for download. Click 'Download' to save them to your local drive."
                  }
                </Text>
              </div>

              {/* Migration Telemetry Dashboard */}
              {telemetryData && (
                <div style={{ maxWidth: '800px', margin: '0 auto', padding: '0 16px 96px 16px' }}>

                  {/* Migration Overview Card */}
                  <Card style={{ marginBottom: '16px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <Text size={500} weight="semibold">Migration Overview</Text>
                      <span style={{ fontSize: '12px', color: '#888' }}>
                        {telemetryData.conversion_metrics?.platform_detected || 'Unknown'} → Azure Kubernetes Service
                      </span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
                      {/* Total Time */}
                      <div style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                        <div style={{ fontSize: '11px', color: '#888', marginBottom: '4px' }}>Total Time</div>
                        <div style={{ fontSize: '20px', fontWeight: '600', color: '#333' }}>
                          {(() => {
                            const timings = telemetryData.step_timings || {};
                            const total = Object.values(timings).reduce((sum: number, t: any) => sum + (t?.elapsed_seconds || 0), 0);
                            const mins = Math.floor(total / 60);
                            const secs = Math.floor(total % 60);
                            return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
                          })()}
                        </div>
                      </div>
                      {/* Platform */}
                      <div style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                        <div style={{ fontSize: '11px', color: '#888', marginBottom: '4px' }}>Source Platform</div>
                        <div style={{ fontSize: '20px', fontWeight: '600', color: '#0078d4' }}>
                          {telemetryData.conversion_metrics?.platform_detected || 'N/A'}
                        </div>
                      </div>
                      {/* Accuracy */}
                      {telemetryData.step_results?.yaml?.result && (
                        <div style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#888', marginBottom: '4px' }}>Conversion Accuracy</div>
                          <div style={{ fontSize: '20px', fontWeight: '600', color: '#107c10' }}>
                            {(() => {
                              const yamlResult = Array.isArray(telemetryData.step_results.yaml.result)
                                ? telemetryData.step_results.yaml.result[0]
                                : telemetryData.step_results.yaml.result;
                              return yamlResult?.termination_output?.overall_conversion_metrics?.overall_accuracy || 'N/A';
                            })()}
                          </div>
                        </div>
                      )}
                      {/* Enterprise Readiness */}
                      <div style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                        <div style={{ fontSize: '11px', color: '#888', marginBottom: '4px' }}>Readiness</div>
                        <div style={{ fontSize: '16px', fontWeight: '600', color: '#107c10' }}>
                          {telemetryData.conversion_metrics?.enterprise_readiness?.split('–')[0]?.trim() || 'N/A'}
                        </div>
                      </div>
                    </div>
                  </Card>

                  {/* Step Timeline */}
                  {telemetryData.step_timings && Object.keys(telemetryData.step_timings).length > 0 && (
                    <Card style={{ marginBottom: '16px', padding: '16px' }}>
                      <Text size={500} weight="semibold" style={{ marginBottom: '12px', display: 'block' }}>Step Timeline</Text>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {(() => {
                          const stepOrder = ['analysis', 'design', 'yaml', 'yaml_conversion', 'documentation'];
                          const stepLabels: Record<string, string> = {
                            'analysis': 'Analysis', 'design': 'Design', 'yaml': 'YAML Conversion',
                            'yaml_conversion': 'YAML Conversion', 'documentation': 'Documentation'
                          };
                          const stepIcons: Record<string, string> = {
                            'analysis': '🔍', 'design': '📐', 'yaml': '📄',
                            'yaml_conversion': '📄', 'documentation': '📝'
                          };
                          const timings = telemetryData.step_timings;
                          const totalElapsed = Object.values(timings).reduce((sum: number, t: any) => sum + (t?.elapsed_seconds || 0), 0);
                          const seen = new Set<string>();

                          return stepOrder
                            .filter(key => {
                              if (!timings[key] || seen.has(stepLabels[key])) return false;
                              seen.add(stepLabels[key]);
                              return true;
                            })
                            .map(key => {
                              const t = timings[key];
                              const elapsed = t?.elapsed_seconds || 0;
                              const pct = totalElapsed > 0 ? (elapsed / totalElapsed) * 100 : 0;
                              const mins = Math.floor(elapsed / 60);
                              const secs = Math.floor(elapsed % 60);
                              const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;

                              // Get step summary from step_results
                              const stepResult = telemetryData.step_results?.[key];
                              let summary = '';
                              if (stepResult?.result) {
                                const r = Array.isArray(stepResult.result) ? stepResult.result[0] : stepResult.result;
                                if (key === 'analysis') {
                                  summary = `${r?.output?.platform_detected || ''} detected (${r?.output?.confidence_score || ''})`;
                                } else if (key === 'yaml' || key === 'yaml_conversion') {
                                  const metrics = r?.termination_output?.overall_conversion_metrics;
                                  if (metrics) summary = `${metrics.successful_conversions}/${metrics.total_files} files converted (${metrics.overall_accuracy})`;
                                } else if (key === 'design') {
                                  const services = r?.termination_output?.azure_services?.length || 0;
                                  const decisions = r?.termination_output?.architecture_decisions?.length || 0;
                                  if (services) summary = `${services} Azure services, ${decisions} architecture decisions`;
                                } else if (key === 'documentation') {
                                  summary = 'Migration report finalized, all sign-offs PASS';
                                }
                              }

                              return (
                                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                  <span style={{ fontSize: '16px', width: '24px', textAlign: 'center' }}>{stepIcons[key] || '✅'}</span>
                                  <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                      <Text weight="semibold" size={300}>{stepLabels[key]}</Text>
                                      <Text size={200} style={{ color: '#666' }}>{timeStr}</Text>
                                    </div>
                                    <div style={{ height: '6px', backgroundColor: '#f0f0f0', borderRadius: '3px', overflow: 'hidden' }}>
                                      <div style={{
                                        width: `${pct}%`, height: '100%',
                                        backgroundColor: t?.ended_at ? '#107c10' : '#0078d4',
                                        borderRadius: '3px', transition: 'width 0.5s'
                                      }} />
                                    </div>
                                    {summary && (
                                      <Text size={200} style={{ color: '#888', marginTop: '2px', display: 'block' }}>{summary}</Text>
                                    )}
                                  </div>
                                </div>
                              );
                            });
                        })()}
                      </div>
                    </Card>
                  )}

                  {/* Agent Participation */}
                  {telemetryData.agent_activities && Object.keys(telemetryData.agent_activities).length > 0 && (
                    <Card style={{ marginBottom: '16px', padding: '16px' }}>
                      <Text size={500} weight="semibold" style={{ marginBottom: '12px', display: 'block' }}>Agent Participation</Text>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {(() => {
                          const agents = telemetryData.agent_activities;
                          const agentIcons: Record<string, string> = {
                            'Coordinator': '⚡', 'Chief Architect': '👷', 'AKS Expert': '☁️',
                            'EKS Expert': '🔍', 'GKE Expert': '🔍', 'YAML Expert': '🔧',
                            'Technical Writer': '📝', 'QA Engineer': '✅', 'Azure Architect': '🏗️'
                          };
                          const stepLabels: Record<string, string> = {
                            'analysis': 'Analysis', 'design': 'Design', 'yaml': 'YAML',
                            'yaml_conversion': 'YAML', 'documentation': 'Docs'
                          };

                          return Object.entries(agents)
                            .filter(([name]) => name !== 'Coordinator')
                            .map(([name, agent]: [string, any]) => {
                              const history = agent.activity_history || [];
                              const actionCount = history.length;
                              const steps = [...new Set(history.map((h: any) => stepLabels[h.step] || h.step).filter(Boolean))];
                              const toolCount = history.filter((h: any) => h.tool_used).length;
                              return { name, actionCount, steps, toolCount };
                            })
                            .sort((a, b) => b.actionCount - a.actionCount)
                            .map(({ name, actionCount, steps, toolCount }) => (
                              <div key={name} style={{
                                display: 'flex', alignItems: 'center', gap: '8px',
                                padding: '6px 8px', backgroundColor: '#f8f9fa', borderRadius: '6px'
                              }}>
                                <span style={{ fontSize: '14px', width: '20px', textAlign: 'center' }}>
                                  {agentIcons[name] || '🤖'}
                                </span>
                                <Text weight="semibold" size={300} style={{ minWidth: '120px' }}>{name}</Text>
                                <span style={{
                                  fontSize: '11px', color: '#0078d4', backgroundColor: '#e8f4fd',
                                  padding: '1px 8px', borderRadius: '10px'
                                }}>
                                  {actionCount} actions
                                </span>
                                {toolCount > 0 && (
                                  <span style={{ fontSize: '11px', color: '#666' }}>🔧 {toolCount} tool calls</span>
                                )}
                                <span style={{ fontSize: '11px', color: '#888', marginLeft: 'auto' }}>
                                  {steps.join(', ')}
                                </span>
                              </div>
                            ));
                        })()}
                      </div>
                    </Card>
                  )}

                </div>
              )}
            </div>
          </>
        );
      }

      // Otherwise show the regular summary view with errors/warnings
      return (
        <>
          {renderHeader()}
          <div className={styles.summaryContent}
            style={{
              width: isPanelOpen ? "calc(100% - 340px)" : "96%",
              transition: "width 0.3s ease-in-out",
            }}>
            {/* Only show success card if at least one file was successfully completed */}
            {batchSummary.completed_files > 0 && (
              <Card className={styles.summaryCard}>
                <div style={{ padding: "8px" }}>
                  <Text weight="semibold">
                    {batchSummary.completed_files} {batchSummary.completed_files === 1 ? 'file' : 'files'} processed successfully
                  </Text>
                </div>
              </Card>
            )}

            {/* Add margin/spacing between cards */}
            <div style={{ marginTop: "16px" }}>
              {renderErrorSection(batchSummary, expandedSections, setExpandedSections, styles)}
            </div>
          </div>
        </>
      );
    }

    return null;
  };

  const handleLeave = () => {
    setShowLeaveDialog(false);
    navigate("/");
  };

  const handleHeaderClick = () => {
    setShowLeaveDialog(true);
  };

  const handleTogglePanel = () => {
    console.log("Toggling panel from BatchView"); // Debugging Log
    setIsPanelOpen((prev) => !prev);
  };

  const handleDownloadZip = async () => {
    if (batchId) {
      try {
        const blob = await apiService.downloadBlob(`/process/${uploadId}/download`);
        const url = window.URL.createObjectURL(blob);

        // Create a temporary <a> element and trigger download
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", "download.zip"); // Specify a filename
        document.body.appendChild(link);
        link.click();

        // Cleanup
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (error) {
        console.error("Download failed:", error);
      }
    }
  };



  if (!dataLoaded && loading) {
    return (
      <div className={styles.root}>
        <Header subtitle="Container Migration" onTitleClick={handleHeaderClick}>
          <HeaderTools>
          </HeaderTools>
        </Header>
        <div className={styles.loadingContainer} style={{ flex: 1 }}>
          <Spinner size="large" />
          <Text size={500}>Loading batch data...</Text>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      <Header subtitle="Container Migration" onTitleClick={handleHeaderClick}>
        <HeaderTools>
        </HeaderTools>
      </Header>

      <div className={styles.content}>
        <PanelLeft panelWidth={400} panelResize={true}>
          <div className={styles.panelHeader} style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "8px 16px 8px 16px",
            marginTop: "15px",
            minHeight: "auto"
          }}>
            <Text weight="semibold">{batchTitle}</Text>
            <Button
              appearance="primary"
              size="medium"
              onClick={handleDownloadZip}
              icon={<ArrowDownload24Regular />}
              disabled={!batchSummary || batchSummary.hasFiles <= 0}
              style={{
                fontSize: "13px",
                height: "32px",
                paddingLeft: "12px",
                paddingRight: "12px"
              }}
            >
              Download as zip
            </Button>
          </div>

          <div className={styles.fileList}>
            {files.map((file) => (
              <div
                key={file.id}
                className={`${styles.fileCard} ${selectedFileId === file.id ? styles.selectedCard : ""}`}
                onClick={() => setSelectedFileId(file.id)}
              >
                {file.id === "summary" ? (
                  // If you have a custom icon, use it here
                  <img src="/images/Docicon.png" alt="Summary icon" className={styles.fileIcon} />
                ) : (
                  <DocumentRegular className={styles.fileIcon} />
                )}
                <Text className={styles.fileName}>{file.name}</Text>
                <div className={styles.statusContainer}>
                  {file.id === "summary" && file.errorCount ? (
                    <>
                      <Text>{file.errorCount} {file.errorCount === 1 ? 'error' : 'errors'}</Text>
                    </>
                  ) : file.status?.toLowerCase() === "error" ? (
                    <>
                      <Text>{file.errorCount}</Text>
                      <DismissCircle24Regular style={{ color: tokens.colorStatusDangerForeground1, width: "16px", height: "16px" }} />
                    </>
                  ) : file.id !== "summary" && file.status === "completed" && file.warningCount ? (
                    <>
                      <Text>{file.warningCount}</Text>
                      <Warning24Regular style={{ color: "#B89500", width: "16px", height: "16px" }} />
                    </>
                  ) : file.status?.toLowerCase() === "completed" ? (
                    <CheckmarkCircle24Regular style={{ color: "0B6A0B", width: "16px", height: "16px" }} />
                  ) : (
                    // No icon for other statuses
                    null
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* <div className={styles.buttonContainer}>
            <Button appearance="secondary" onClick={() => navigate("/")}>
              Return home
            </Button>
          </div> */}
        </PanelLeft>
        {isPanelOpen && (
          <div
            style={{
              position: "fixed",
              top: "60px", // Adjust based on your header height
              right: 0,
              height: "calc(100vh - 60px)", // Ensure it does not cover the header
              width: "300px", // Set an appropriate width
              zIndex: 1050,
              background: "white",
              overflowY: "auto",
            }}
          >
            <PanelRight panelWidth={300} panelResize={true} panelType={"first"} >
              <PanelRightToolbar panelTitle="Batch history" panelIcon={<History />} handleDismiss={handleTogglePanel} />
              <BatchHistoryPanel isOpen={isPanelOpen} onClose={() => setIsPanelOpen(false)} />
            </PanelRight>
          </div>
        )}
        <Content>
          <div className={styles.mainContent}>{renderContent()}</div>
        </Content>

      </div>
      <ConfirmationDialog
        open={showLeaveDialog}
        setOpen={setShowLeaveDialog}
        title="Return to home page?"
        message="Are you sure you want to navigate away from this batch view?"
        onConfirm={handleLeave}
        onCancel={() => setShowLeaveDialog(false)}
        confirmText="Return to home"
        cancelText="Stay here"
      />
    </div>
  );
};

export default BatchStoryPage;
