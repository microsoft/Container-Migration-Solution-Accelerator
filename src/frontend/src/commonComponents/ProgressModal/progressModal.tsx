import React from "react";
import { 
  Dialog, 
  DialogSurface, 
  DialogBody, 
  DialogTitle, 
  DialogContent,
  DialogActions,
  Button 
} from "@fluentui/react-components";
import { Dismiss24Regular } from "@fluentui/react-icons";
import Lottie from 'lottie-react';
import documentLoader from "../../../public/images/loader.json";

interface ProgressModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  title: string;
  currentPhase: string;
  phaseSteps: string[];
  apiData?: any;
  onCancel?: () => void;
  showCancelButton?: boolean;
  processingCompleted?: boolean;
  migrationError?: boolean;
  onNavigateHome?: () => void;
}

const ProgressModal: React.FC<ProgressModalProps> = ({
  open,
  setOpen,
  title,
  currentPhase,
  phaseSteps,
  apiData,
  onCancel,
  showCancelButton = true,
  processingCompleted = false,
  migrationError = false,
  onNavigateHome
}) => {
  // Calculate progress percentage based on step (stable step-level identifier)
  const getProgressPercentage = () => {
    if (migrationError) return 0; // Show 0% progress for errors
    if (processingCompleted && !migrationError) return 100;
    if (!apiData) return 0;

    // Use apiData.step (stable: "analysis", "design", "yaml_conversion", "documentation")
    // rather than apiData.phase which changes to sub-phase names like "Platform Enhancement"
    const steps = ['analysis', 'design', 'yaml_conversion', 'documentation'];
    const currentStepIndex = steps.indexOf((apiData.step || '').toLowerCase());

    if (currentStepIndex === -1) return 0;

    // Each step represents 25% of the progress
    const baseProgress = (currentStepIndex / steps.length) * 100;

    // Add some progress within the current step
    const stepProgress = Math.min(20, (currentStepIndex + 1) * 5);

    return Math.min(95, baseProgress + stepProgress);
  };

  const progressPercentage = getProgressPercentage();

  const handleClose = () => {
    // Just close the modal without triggering onCancel
    setOpen(false);
  };

  const handleCancel = () => {
    // Trigger onCancel (navigate to landing page) and close modal
    if (onCancel) {
      onCancel();
    }
    setOpen(false);
  };

  return (
    <Dialog 
      open={open} 
      onOpenChange={(event, data) => {
        // Just close the modal without triggering onCancel
        setOpen(data.open);
      }}
      modalType="modal"
    >
      <DialogSurface style={{ minWidth: '500px', maxWidth: '700px' }}>
        <DialogBody>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <DialogTitle>{title}</DialogTitle>
            {!processingCompleted && (
              <Button 
                appearance="subtle" 
                icon={<Dismiss24Regular />} 
                onClick={handleClose}
                style={{
                  position: "absolute",
                  top: "8px",
                  right: "8px",
                  width: "32px",
                  height: "32px",
                }}
              />
            )}
          </div>
          
          <DialogContent>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Current Phase Display */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '40px', height: '40px' }}>
                  {!processingCompleted ? (
                    <Lottie 
                      animationData={documentLoader} 
                      loop={true} 
                      style={{ width: '100%', height: '100%' }}
                    />
                  ) : (
                    <div style={{ 
                      fontSize: '24px', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center',
                      width: '100%',
                      height: '100%'
                    }}>
                      {migrationError ? '❌' : '✅'}
                    </div>
                  )}
                </div>
                <div>
                  <div style={{ fontWeight: '600', fontSize: '16px' }}>
                    {migrationError ? 'Migration Failed!' : 
                     processingCompleted ? 'Migration Completed!' : 
                     `${currentPhase || 'Processing'} Phase`}
                  </div>
                  <div style={{ fontSize: '14px', color: '#666' }}>
                    {migrationError ? 'The migration stopped before completion.' :
                     processingCompleted ? 'Your container migration is ready!' : 
                     'Converting your container workloads...'}
                  </div>
                </div>
              </div>

              {/* Progress Bar */}
              <div style={{ width: '100%' }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: '8px'
                }}>
                  <span style={{ fontSize: '14px', fontWeight: '500' }}>Progress</span>
                  <span style={{ fontSize: '14px', color: '#666' }}>{Math.round(progressPercentage)}%</span>
                </div>
                <div style={{
                  width: '100%',
                  height: '8px',
                  backgroundColor: '#f0f0f0',
                  borderRadius: '4px',
                  overflow: 'hidden'
                }}>
                  <div
                    style={{
                      width: `${progressPercentage}%`,
                      height: '100%',
                      backgroundColor: migrationError ? '#dc3545' : 
                                     processingCompleted ? '#4CAF50' : '#0078d4',
                      borderRadius: '4px',
                      transition: 'width 0.5s ease-in-out'
                    }}
                  />
                </div>
              </div>

              {/* Phase Information */}
              {apiData && (
                <div style={{ 
                  backgroundColor: '#f8f9fa', 
                  padding: '12px', 
                  borderRadius: '6px',
                  fontSize: '14px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: '500' }}>Current Activity:</span>
                    {(() => {
                      // Show step-level elapsed time from step_timings
                      const stepTimings = apiData.step_timings || {};
                      const currentStep = (apiData.step || '').toLowerCase();
                      const timing = stepTimings[currentStep];
                      if (timing?.started_at) {
                        try {
                          const started = new Date(timing.started_at.replace(' UTC', 'Z'));
                          const diffSec = Math.max(0, Math.floor((Date.now() - started.getTime()) / 1000));
                          let elapsed = '';
                          if (diffSec < 60) elapsed = `${diffSec}s`;
                          else if (diffSec < 3600) elapsed = `${Math.floor(diffSec / 60)}m ${diffSec % 60}s`;
                          else elapsed = `${Math.floor(diffSec / 3600)}h ${Math.floor((diffSec % 3600) / 60)}m`;
                          return (
                            <span style={{ fontSize: '12px', color: '#888' }}>
                              ⏱ {elapsed}
                            </span>
                          );
                        } catch { /* ignore */ }
                      }
                      return null;
                    })()}
                  </div>
                  {(() => {
                    // Parse all active agents from raw telemetry strings
                    const activeAgents = (apiData.agents || []).filter((agent: string) =>
                      agent.startsWith('✓')
                    );

                    if (activeAgents.length === 0) {
                      return (
                        <div style={{ color: '#666' }}>
                          Working on {currentPhase?.toLowerCase()} phase...
                        </div>
                      );
                    }

                    return activeAgents.map((raw: string, idx: number) => {
                      // Strip prefix: "✓[🤔🔥] " → ""
                      const cleaned = raw.replace(/^[✓✗]\[.*?\]\s*/, '');
                      // Agent name: everything before first ":"
                      const colonIdx = cleaned.indexOf(':');
                      const agentName = colonIdx > 0 ? cleaned.substring(0, colonIdx).trim() : 'Agent';

                      // Determine action from status keywords
                      const actionIcons: Record<string, { icon: string; label: string }> = {
                        'speaking':  { icon: '🗣️', label: 'Speaking' },
                        'thinking':  { icon: '💭', label: 'Thinking' },
                        'using_tool':{ icon: '🔧', label: 'Invoking Tool' },
                        'analyzing': { icon: '🔍', label: 'Analyzing' },
                        'responded': { icon: '✅', label: 'Responded' },
                        'ready':     { icon: '⏳', label: 'Ready' },
                      };
                      const statusPart = colonIdx > 0 ? cleaned.substring(colonIdx + 1) : cleaned;
                      let actionInfo = { icon: '⚡', label: 'Working' };
                      for (const [key, info] of Object.entries(actionIcons)) {
                        if (statusPart.toLowerCase().includes(key)) {
                          actionInfo = info;
                          break;
                        }
                      }

                      // Extract tool name(s) from 🔧 segment
                      const toolMatch = raw.match(/🔧\s*([^|]+)/);
                      let toolName = '';
                      if (toolMatch) {
                        // Clean up: take tool names, strip long JSON args
                        toolName = toolMatch[1]
                          .trim()
                          .replace(/\{[^}]*\}\.*/g, '')  // remove JSON snippets
                          .replace(/\(.*?\)/g, '')        // remove parenthesized args
                          .replace(/,\s*$/, '')
                          .trim();
                        if (toolName) {
                          actionInfo = { icon: '🔧', label: 'Invoking Tool' };
                        }
                      }

                      // Extract action count from 📊 segment
                      const actionsMatch = raw.match(/📊\s*(\d+)\s*actions?/);
                      const actionCount = actionsMatch ? parseInt(actionsMatch[1]) : 0;

                      // Extract blocking info from 🚧 segment
                      const blockingMatch = raw.match(/🚧\s*Blocking\s*(\d+)/);
                      const blockingCount = blockingMatch ? parseInt(blockingMatch[1]) : 0;

                      return (
                        <div key={idx} style={{
                          marginBottom: idx < activeAgents.length - 1 ? '10px' : 0,
                          padding: '8px 10px',
                          backgroundColor: 'white',
                          borderRadius: '6px',
                          border: '1px solid #e8e8e8',
                        }}>
                          {/* Agent name + action */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                            <span style={{ fontSize: '15px' }}>{actionInfo.icon}</span>
                            <span style={{ fontWeight: '600', color: '#333' }}>{agentName}</span>
                            <span style={{ 
                              fontSize: '12px', 
                              color: '#0078d4', 
                              backgroundColor: '#e8f4fd',
                              padding: '1px 8px',
                              borderRadius: '10px',
                              fontWeight: '500'
                            }}>
                              {actionInfo.label}
                            </span>
                          </div>
                          {/* Tool + metrics row */}
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', fontSize: '12px', color: '#666' }}>
                            {toolName && (
                              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                                <span>🔧</span> {toolName}
                              </span>
                            )}
                            {actionCount > 0 && (
                              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                                <span>📊</span> {actionCount} action{actionCount !== 1 ? 's' : ''}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    });
                  })()}
                  {apiData.active_agent_count != null && apiData.total_agents != null && (
                    <div style={{ marginTop: '8px', fontSize: '12px', color: '#888' }}>
                      {apiData.active_agent_count}/{apiData.total_agents} agents active
                      {apiData.health_status?.includes('🟢') && ' 🟢'}
                    </div>
                  )}
                </div>
              )}

              {/* Recent Steps */}
              {phaseSteps.length > 0 && (
                <div>
                  <div style={{ fontWeight: '500', marginBottom: '8px', fontSize: '14px' }}>
                    Recent Activity:
                  </div>
                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {[...phaseSteps].reverse().slice(0, 5).map((step, index) => (
                      <div 
                        key={index}
                        style={{ 
                          fontSize: '13px', 
                          color: '#666',
                          padding: '6px 8px',
                          backgroundColor: 'white',
                          borderRadius: '4px',
                          border: '1px solid #e0e0e0'
                        }}
                      >
                        {step}
                      </div>
                    ))}
                  </div>
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
          
          {showCancelButton && !processingCompleted && (
            <DialogActions>
              <Button 
                appearance="primary" 
                onClick={handleClose}
              >
                Continue
              </Button>
              <Button 
                appearance="secondary" 
                onClick={handleCancel}
              >
                Cancel Processing
              </Button>
            </DialogActions>
          )}
          
          {processingCompleted && (
            <DialogActions>
              {migrationError && onNavigateHome && (
                <Button 
                  appearance="secondary" 
                  onClick={onNavigateHome}
                >
                  Back to Home
                </Button>
              )}
              <Button 
                appearance="primary" 
                onClick={() => setOpen(false)}
              >
                View Results
              </Button>
            </DialogActions>
          )}
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
};

export default ProgressModal;
