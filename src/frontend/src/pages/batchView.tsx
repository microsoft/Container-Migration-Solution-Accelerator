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
import { vs } from "react-syntax-highlighter/dist/esm/styles/hljs"
import ReactMarkdown from "react-markdown"
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
            <div className={styles.codeHeader}>
              <Text weight="semibold">
                {selectedFile.name} {selectedFileTranslatedContent && getFileLanguageAndType(selectedFile.name).language !== 'markdown' ? "(Migrated)" : ""}
              </Text>
            </div>
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
                    <div style={{
                      margin: 0,
                      padding: "16px",
                      backgroundColor: tokens.colorNeutralBackground1,
                      borderRadius: "4px",
                      overflow: "auto",
                      maxHeight: "70vh"
                    }}>
                      <ReactMarkdown>{selectedFileTranslatedContent}</ReactMarkdown>
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
                  marginTop: '60px',
                  height: '70vh',
                  width: "100%", // Ensures full visibility
                  maxWidth: "800px", // Prevents content from stretching
                  margin: "auto", // Keeps it centered
                  transition: "width 0.3s ease-in-out",
                }}>
                <img
                  src={getJsonYamlFileCount() === 0 ? "/images/Crossmark.png" : "/images/Checkmark.png"}
                  alt={getJsonYamlFileCount() === 0 ? "No files" : "Success checkmark"}
                  style={{ width: '150px', height: '150px', marginBottom: '24px' }}
                />
                <Text size={600} weight="semibold" style={{ marginBottom: '16px' }}>
                  {getJsonYamlFileCount() === 0 ? "No files to process!" : "No errors! Your files are ready to download."}
                </Text>
                <Text style={{ marginBottom: '24px' }}>
                  {getJsonYamlFileCount() === 0 
                    ? "No files were found in this migration batch. Please upload files to proceed with the migration process."
                    : "Your files have been successfully migrated with no errors. All files are now ready for download. Click 'Download' to save them to your local drive."
                  }
                </Text>
              </div>
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
        <div onClick={handleHeaderClick} style={{ cursor: "pointer" }}>
          <Header subtitle="Container Migration">
            <div onClick={(e) => e.stopPropagation()}>
              <HeaderTools>
              </HeaderTools>
            </div>
          </Header>
        </div>
        <div className={styles.loadingContainer} style={{ flex: 1 }}>
          <Spinner size="large" />
          <Text size={500}>Loading batch data...</Text>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      <div onClick={handleHeaderClick} style={{ cursor: "pointer" }}>
        <Header subtitle="Container Migration">
          <div onClick={(e) => e.stopPropagation()}>
            <HeaderTools>
            </HeaderTools>
          </div>
        </Header>
      </div>

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