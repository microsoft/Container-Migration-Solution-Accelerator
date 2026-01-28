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
  // Calculate progress percentage based on phases
  const getProgressPercentage = () => {
    if (migrationError) return 0; // Show 0% progress for errors
    if (!apiData || !apiData.phase) return 0;
    
    const phases = ['Analysis', 'Design', 'YAML', 'Documentation'];
    const currentPhaseIndex = phases.indexOf(apiData.phase);
    
    if (currentPhaseIndex === -1) return 0;
    if (processingCompleted && !migrationError) return 100;
    
    // Each phase represents 25% of the progress
    const baseProgress = (currentPhaseIndex / phases.length) * 100;
    
    // Add some progress within the current phase based on time elapsed
    const phaseProgress = Math.min(20, (currentPhaseIndex + 1) * 5);
    
    return Math.min(95, baseProgress + phaseProgress);
  };

  const progressPercentage = getProgressPercentage();

  const handleClose = () => {
    // Just close the modal without triggering onCancel
    setOpen(false);
  };

  const handleCancel = async () => {
    console.log('=== ProgressModal handleCancel called ===');
    // Trigger onCancel (calls cancel API and navigates to landing page) and close modal
    if (onCancel) {
      console.log('Calling onCancel callback...');
      await onCancel();
      console.log('onCancel callback completed');
    } else {
      console.warn('No onCancel callback provided');
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
                  <div style={{ fontWeight: '500', marginBottom: '4px' }}>Current Activity:</div>
                  <div style={{ color: '#666' }}>
                    {apiData.agents?.find(agent => agent.includes('speaking') || agent.includes('thinking')) || 
                     `Working on ${currentPhase?.toLowerCase()} phase...`}
                  </div>
                  {apiData.active_agent_count && apiData.total_agents && (
                    <div style={{ marginTop: '8px', fontSize: '12px', color: '#888' }}>
                      {apiData.active_agent_count}/{apiData.total_agents} agents active
                      {apiData.health_status?.includes('🟢') && ' 🟢'}
                    </div>
                  )}
                </div>
              )}

              {/* Recent Steps */}
              {phaseSteps.length > 0 && (
                <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  <div style={{ fontWeight: '500', marginBottom: '8px', fontSize: '14px' }}>
                    Recent Activity:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {phaseSteps.slice(-5).map((step, index) => (
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
