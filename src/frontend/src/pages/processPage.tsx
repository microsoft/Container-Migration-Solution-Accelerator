import React, { useState, useEffect, useRef } from "react";
import { useSelector, useDispatch } from "react-redux";
import { useNavigate, useParams } from "react-router-dom";
import { RootState } from "../store/store";
import { togglePanel, closePanel } from "../slices/historyPanelSlice";
import {
  Button,
  Tooltip,
} from "@fluentui/react-components";
import { MessageBar, MessageBarType } from "@fluentui/react";
import Header from "../components/Header/Header";
import HeaderTools from "../components/Header/HeaderTools";
import PanelRightToolbar from "../components/Panels/PanelRightToolbar";
import PanelRight from "../components/Panels/PanelRight";
import BatchHistoryPanel from "../components/batchHistoryPanel";
import { HistoryRegular, HistoryFilled, bundleIcon } from "@fluentui/react-icons";
import { CircleCheck, X } from "lucide-react";
import Lottie from 'lottie-react';
import documentLoader from "../../public/images/loader.json";
import { getApiUrl, headerBuilder } from '../api/config';
import { apiService } from '../services/ApiService';
import ProgressModal from "../commonComponents/ProgressModal/progressModal";

export const History = bundleIcon(HistoryFilled, HistoryRegular);

// Custom scrollbar styles for better accessibility
const scrollbarStyles = `
  .custom-scrollbar {
    scrollbar-width: thin;
    scrollbar-color: #888 #f1f1f1;
  }
  
  .custom-scrollbar::-webkit-scrollbar {
    width: 8px;
  }
  
  .custom-scrollbar::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
  }
  
  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 4px;
  }
  
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: #555;
  }

  /* Ensure main content area has visible scrollbars */
  .main-content {
    scrollbar-width: thin;
    scrollbar-color: #888 #f1f1f1;
  }

  .main-content::-webkit-scrollbar {
    width: 8px;
  }
  
  .main-content::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
  }
  
  .main-content::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 4px;
  }
  
  .main-content::-webkit-scrollbar-thumb:hover {
    background: #555;
  }

  /* Responsive adjustments for larger screens */
  @media (min-width: 1920px) {
    .bg-gray-50 {
      padding: 2rem !important;
    }
    
    .text-2xl {
      font-size: 2.5rem !important;
    }
    
    .text-lg {
      font-size: 1.5rem !important;
    }
  }

  @media (min-width: 1400px) and (max-width: 1919px) {
    .bg-gray-50 {
      padding: 1.5rem !important;
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

const ProcessPage: React.FC = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { batchId } = useParams<{ batchId: string }>();
  const isPanelOpen = useSelector((state: RootState) => state.historyPanel.isOpen);

  // New state for real-time API data
  const [currentPhase, setCurrentPhase] = useState<string>("");
  const [phaseSteps, setPhaseSteps] = useState<string[]>([]);
  const [apiData, setApiData] = useState<any>(null);
  const [lastUpdateTime, setLastUpdateTime] = useState<string>("");
  const [processingCompleted, setProcessingCompleted] = useState(false);
  const stepsContainerRef = useRef<HTMLDivElement>(null);

  // Progress modal state
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [processingState, setProcessingState] = useState<'IDLE' | 'PROCESSING' | 'COMPLETED'>('IDLE');

  // Error state management
  const [migrationError, setMigrationError] = useState(false);

  // Helper function to generate phase message from API data
  const getPhaseMessage = (apiResponse: any) => {
    if (!apiResponse) return "";

    const { phase, active_agent_count, total_agents, health_status, agents } = apiResponse;

    const phaseMessages = {
      'Analysis': 'Analyzing workloads and dependencies, existing container images and configurations',
      'Design': 'Designing target environment mappings to align with Azure AKS',
      'YAML': 'Converting container specifications and orchestration configs to Azure format',
      'Documentation': 'Generating migration report and deployment files'
    };

    // Extract active agent information from agents array
    const activeAgents = agents?.filter(agent =>
      agent.includes('speaking') || agent.includes('thinking')
    ) || [];

    const speakingAgent = activeAgents.find(agent => agent.includes('speaking'));
    const thinkingAgent = activeAgents.find(agent => agent.includes('thinking'));

    let agentActivity = "";
    if (speakingAgent) {
      const agentName = speakingAgent.split(':')[0].replace(/[✓✗]/g, '').replace(/\[.*?\]/g, '').trim();
      agentActivity = ` - ${agentName} is speaking`;
    } else if (thinkingAgent) {
      const agentName = thinkingAgent.split(':')[0].replace(/[✓✗]/g, '').replace(/\[.*?\]/g, '').trim();
      agentActivity = ` - ${agentName} is thinking`;
    }

    const baseMessage = phaseMessages[phase] || `${phase} phase in progress`;
    const agentInfo = active_agent_count && total_agents ? ` (${active_agent_count}/${total_agents} agents active)` : '';
    const healthIcon = health_status?.includes('🟢') ? ' 🟢' : '';

    return `${phase} phase: ${baseMessage}${agentActivity}${agentInfo}`;
  };

  // Polling function to check batch status
  const pollBatchStatus = async () => {
    if (!batchId) return;

    try {
      const response = await apiService.get(`/process/status/${batchId}/render/`);

      if (!response) {
        console.error('No response received from status endpoint');
        return;
      }
      console.log('Polling batch status:', response);

      // Store API data for real-time display
      setApiData(response);

      // Update processing state and show modal when processing starts
      if (response.status === 'processing' && processingState !== 'PROCESSING') {
        setProcessingState('PROCESSING');
        setShowProgressModal(true);
      }

      // Check if last_update_time has changed - only update if there's new activity
      if (response.last_update_time && response.last_update_time !== lastUpdateTime) {
        console.log('New activity detected! Last update time changed from', lastUpdateTime, 'to', response.last_update_time);

        // Update the stored last update time
        setLastUpdateTime(response.last_update_time);

        // Update current phase and generate step message
        if (response.phase) {
          const newPhaseMessage = getPhaseMessage(response);

          // Add the new message to steps ONLY if it's different from the last message
          setCurrentPhase(response.phase);
          setPhaseSteps(prev => {
            // Check if the new message is different from the last message
            const lastMessage = prev[prev.length - 1];
            if (lastMessage !== newPhaseMessage) {
              console.log('Adding new unique message:', newPhaseMessage);
              return [...prev, newPhaseMessage];
            } else {
              console.log('Skipping duplicate message even though timestamp changed:', newPhaseMessage);
              return prev;
            }
          });
        }
      } else if (response.last_update_time) {
        console.log('No new activity - last update time unchanged:', response.last_update_time);
      }

      // Check for completion and navigate to batch-view
      if (response.status === 'completed') {
        console.log('Migration completed! Navigating to batch view page...');
        setProcessingCompleted(true);
        setProcessingState('COMPLETED');
        // Add completion message
        setPhaseSteps(prev => [...prev, "✅ Migration completed successfully! Redirecting to results..."]);
        // Navigate to the batch view page after a short delay
        setTimeout(() => {
          navigate(`/batch-view/${batchId}`);
        }, 2000); // 2 second delay to show completion
      }

      // Check for error/failure status
      if (response.status === 'failed' || response.status === 'error') {
        console.log('Migration failed! Status:', response.status);
        setMigrationError(true);
        setProcessingState('IDLE');
        setProcessingCompleted(true); // Stop polling
        // Add error message to steps
        setPhaseSteps(prev => [...prev, "❌ Migration failed - stopping process..."]);
      }
    } catch (error) {
      console.error('Error polling batch status:', error);
    }
  };

  // COMMENTED OUT - Old static steps logic
  /*
  const steps = [
    "Analyzing workloads and dependencies, existing container images and configurations...",
    "Designing target environment mappings to align with Azure AKS...",
    "Converting container specifications and orchestration configs to the new environment...",
    "Generating migration report and deployment files...",
    "Analyzing workloads and dependencies, existing container images and configurations...",
    "Designing target environment mappings to align with Azure AKS...",
    "Converting container specifications and orchestration configs to the new environment...",
    "Generating migration report and deployment files...",
    "Analyzing workloads and dependencies, existing container images and configurations...",
    "Designing target environment mappings to align with Azure AKS...",
    "Converting container specifications and orchestration configs to the new environment...",
    "Generating migration report and deployment files..."
  ];
  */

  // COMMENTED OUT - Old progressive step display logic
  /*
  // Progressive step display that keeps appending cycles
  useEffect(() => {
    let stepTimer: ReturnType<typeof setTimeout>;
    
    const addNextStep = () => {
      setVisibleStepsCount(prev => {
        const newCount = prev + 1;
        
        // After every 4 steps, increment the cycle count
        if (newCount % 4 === 0) {
          setTotalCycles(prevCycles => prevCycles + 1);
        }
        
        return newCount;
      });
      
      // Schedule next step in 5 seconds
      stepTimer = setTimeout(addNextStep, 5000);
    };
    
    // Start the first step after 5 seconds
    stepTimer = setTimeout(addNextStep, 5000);

    // Cleanup timer on component unmount
    return () => {
      clearTimeout(stepTimer);
    };
  }, []);
  */

  // Handle modal cancellation
  const handleCancelProcessing = async () => {
    console.log('=== handleCancelProcessing called ===');
    console.log('batchId:', batchId);
    
    // Call API to cancel the process
    if (batchId) {
      try {
        console.log('Calling apiService.cancelProcess with batchId:', batchId);
        const result = await apiService.cancelProcess(batchId, 'User cancelled from UI');
        console.log('Cancel request result:', result);
      } catch (error) {
        console.error('Failed to cancel process:', error);
        // Continue with UI cleanup even if API call fails
      }
    } else {
      console.warn('No batchId available, skipping cancel API call');
    }
    
    setShowProgressModal(false);
    setProcessingState('IDLE');
    // Navigate back to landing page
    navigate('/');
  };

  // Effect to show modal automatically when processing is detected
  useEffect(() => {
    if (apiData && apiData.status === 'processing' && !showProgressModal) {
      setShowProgressModal(true);
      setProcessingState('PROCESSING');
    }
  }, [apiData, showProgressModal]);

  // Polling effect - poll every 5 seconds for batch status
  useEffect(() => {
    if (!batchId || processingCompleted) {
      return;
    }

    console.log('Starting batch status polling every 5 seconds...');

    // Poll immediately on mount
    pollBatchStatus();

    // Set up interval for every 5 seconds
    const pollInterval = setInterval(() => {
      console.log('Polling batch status...');
      pollBatchStatus();
    }, 10000); // Poll every 10 seconds

    return () => {
      console.log('Cleaning up batch status polling');
      clearInterval(pollInterval);
    };
  }, [batchId, processingCompleted]);

  // Auto-scroll effect when new phase steps are added
  useEffect(() => {
    if (stepsContainerRef.current && phaseSteps.length > 0) {
      const container = stepsContainerRef.current;
      // Scroll to bottom with smooth behavior
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [phaseSteps]);

  const handleTogglePanel = () => {
    console.log("Toggling panel from Process Page");
    dispatch(togglePanel());
  };

  const handleLeave = () => {
    // Show progress modal when header is clicked
    setShowProgressModal(true);
  };

  const handleNavigateHome = () => {
    // Navigate back to landing page
    navigate('/');
  };

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: scrollbarStyles }} />
      <div className="landing-page flex flex-col relative h-screen">
        {/* Header - Same as Landing Page */}
        <Header subtitle="Container Migration" onTitleClick={handleLeave}>
          <HeaderTools>
          </HeaderTools>
        </Header>

        {/* Main Content */}
        <main className={`main-content ${isPanelOpen ? "shifted" : ""} flex-1 flex overflow-auto bg-mode-neutral-background-1-rest relative`}>
          <div className="min-h-full flex flex-col items-center bg-gray-50 p-4 sm:p-6 lg:p-8 w-full" style={{ marginTop: 'clamp(20px, 4vh, 60px)', paddingTop: '1rem' }}>
            {/* Header - Centered */}
            <div className="text-center mb-2" style={{ textAlign: 'center' }}>
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-semibold mb-1">Container Migration</h1>
              <p className="text-gray-600 max-w-xl lg:max-w-2xl mx-auto text-sm sm:text-base">
                Migrate your third party container workloads to{" "}
                <a
                  href="https://azure.microsoft.com/en-us/products/kubernetes-service/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Azure AKS
                </a>{" "}
              </p>
            </div>

            {/* Error MessageBar - Between title and Agent Activity */}
            {migrationError && (
              <div style={{
                width: '100%',
                maxWidth: '60vw',
                margin: '0px auto',
                marginBottom: '20px' // Reduced gap from 40px to 20px
              }}>
                <MessageBar
                  messageBarType={MessageBarType.error}
                  isMultiline={true}
                  //onDismiss={() => setMigrationError(false)}
                  dismissButtonAriaLabel="Close"
                  styles={{
                    root: {
                      display: "flex",
                      alignItems: "center",
                      backgroundColor: "#fef2f2",
                      borderColor: "#fca5a5",
                      color: "#991b1b"
                    },
                    text: {
                      fontSize: "14px", // Increased from default (usually 14px)
                    }
                  }}
                >
                  The migration stopped before completion and no results were generated.
                  <br />
                  Please check the logs using Process ID: {batchId} for more details.
                </MessageBar>
              </div>
            )}

            {/* Card */}
            <div className="bg-white border-2 border-gray-300 rounded-2xl shadow-lg p-6 sm:p-8" style={{
              textAlign: 'center',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
              border: '1px solid #d1d5db',
              width: '100%',
              maxWidth: '60vw',
              margin: '10px auto', // Reduced from '0px auto' to bring it closer to header
              borderRadius: '12px',
              paddingBottom: '16px',
              paddingTop: '16px',
            }}>
              {/* Lottie Animation - Centered above Agent Activity */}
              {!migrationError && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  width: '100%',
                  marginBottom: '24px'
                }}>
                  <Lottie
                    animationData={documentLoader}
                    loop={true}
                    style={{
                      width: '120px',
                      height: '120px',
                      margin: '0 auto'
                    }}
                  />
                </div>
              )}

              {/* Title */}
              <h2 className="text-lg font-semibold text-center mb-6" style={{ textAlign: 'center' }}>Agent Activity</h2>

              {/* Real-time phase steps from API */}
              <div
                ref={stepsContainerRef}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  width: '100%',
                  maxWidth: '90%',
                  margin: '0 auto',
                  maxHeight: '240px', // Reduced from 320px to show exactly 4 steps
                  minHeight: '200px',
                  overflowY: 'auto',
                  paddingRight: '8px',
                  scrollbarWidth: 'thin',
                  scrollbarColor: '#888 #f1f1f1'
                }}
                className="custom-scrollbar"
              >
                {phaseSteps.length === 0 ? (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '12px 16px',
                      backgroundColor: '#f9fafb',
                      borderRadius: '8px',
                      border: '1px solid #d1d5db',
                      boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', width: '24px' }}>
                      <CircleCheck
                        strokeWidth="2.5px"
                        color="#203474"
                        size="16px"
                      />
                    </div>
                    <div
                      style={{
                        flex: 1,
                        fontSize: "14px",
                        color: "#666666",
                        textAlign: "left",
                        fontStyle: "italic"
                      }}
                    >
                      Waiting for migration process to start...
                    </div>
                  </div>
                ) : (
                  phaseSteps.map((step, index) => (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        padding: '12px 16px',
                        backgroundColor: step.includes('✅') ? '#f0f9f0' : '#f9fafb',
                        borderRadius: '8px',
                        border: step.includes('✅') ? '1px solid #10b981' : '1px solid #d1d5db',
                        boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                        animation: 'fadeIn 0.5s ease-in-out',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', width: '24px' }}>
                        <CircleCheck
                          strokeWidth="2.5px"
                          color={step.includes('✅') ? "#10b981" : "#203474"}
                          size="16px"
                        />
                      </div>
                      <div
                        style={{
                          flex: 1,
                          fontSize: "14px",
                          color: "#000000",
                          textAlign: "left",
                        }}
                      >
                        {step}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </main>

        {/* Side Panel - Same as Landing Page */}
        {isPanelOpen && (
          <div
            style={{
              position: "fixed",
              top: "60px",
              right: 0,
              height: "calc(100vh - 60px)",
              width: "clamp(260px, 20vw, 320px)", // Responsive width
              zIndex: 1050,
              background: "white",
              overflowY: "auto",
            }}
          >
            <PanelRight panelWidth={300} panelResize={true} panelType={"first"} >
              <PanelRightToolbar panelTitle="Batch history" panelIcon={<History />} handleDismiss={handleTogglePanel} />
              <BatchHistoryPanel isOpen={isPanelOpen} onClose={() => dispatch(closePanel())} />
            </PanelRight>
          </div>
        )}

        {/* Progress Modal */}
        <ProgressModal
          open={showProgressModal}
          setOpen={setShowProgressModal}
          title="Processing Container Migration"
          currentPhase={currentPhase}
          phaseSteps={phaseSteps}
          apiData={apiData}
          onCancel={handleCancelProcessing}
          showCancelButton={true}
          processingCompleted={processingCompleted}
          migrationError={migrationError}
          onNavigateHome={handleNavigateHome}
        />
      </div>
    </>
  );
};

export default ProcessPage;
