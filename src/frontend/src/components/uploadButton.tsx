import React, { useCallback, useState, useEffect } from 'react';
import { useDropzone, FileRejection, DropzoneOptions } from 'react-dropzone';
import { CircleCheck, X, CircleX } from 'lucide-react';
import {
  Button,
  Toast,
  ToastTitle,
  useToastController,
  Tooltip,
} from "@fluentui/react-components";
import { MessageBar, MessageBarType } from "@fluentui/react";
import { deleteBatch, deleteFileFromBatch, createProcess, uploadFiles, startProcessing, deleteFile } from '../slices/batchSlice';
import { useDispatch } from 'react-redux';
import ConfirmationDialog from '../commonComponents/ConfirmationDialog/confirmationDialogue';
import { AppDispatch } from '../store/store'
import { v4 as uuidv4 } from 'uuid';
import "./uploadStyles.css";
import { useNavigate } from "react-router-dom";

interface FileUploadZoneProps {
  onFileUpload?: (acceptedFiles: File[]) => void;
  onFileReject?: (fileRejections: FileRejection[]) => void;
  onUploadStateChange?: (state: 'IDLE' | 'UPLOADING' | 'COMPLETED') => void;
  maxSize?: number;
  acceptedFileTypes?: Record<string, string[]>;
  onStartTranslating?: () => Promise<void>;
}

interface UploadingFile {
  file: File;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  id: string;
  batchId: string;
}

const FileUploadZone: React.FC<FileUploadZoneProps> = ({
  onFileUpload,
  onFileReject,
  onUploadStateChange,
  maxSize = 4 * 1024 * 1024,
  acceptedFileTypes = { 
    'application/x-yaml': ['.yaml', '.yml']
  },
  onStartTranslating
}) => {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [uploadIntervals, setUploadIntervals] = useState<{ [key: string]: ReturnType<typeof setTimeout> }>({});
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showLogoCancelDialog, setShowLogoCancelDialog] = useState(false);
  const [uploadState, setUploadState] = useState<'IDLE' | 'UPLOADING' | 'COMPLETED'>('IDLE');
  const [batchId, setBatchId] = useState<string>('');
  const [allUploadsComplete, setAllUploadsComplete] = useState(false);
  const [fileLimitExceeded, setFileLimitExceeded] = useState(false);
  const [showFileLimitDialog, setShowFileLimitDialog] = useState(false);
  const [isCreatingProcess, setIsCreatingProcess] = useState(false);
  const [rejectedFiles, setRejectedFiles] = useState<FileRejection[]>([]);
  const [showFileRejectionError, setShowFileRejectionError] = useState(false);
  const [showNetworkError, setShowNetworkError] = useState(false);
  const [networkErrorMessage, setNetworkErrorMessage] = useState('');
  const navigate = useNavigate();

  const MAX_FILES = 20;
  const dispatch = useDispatch<AppDispatch>();

  // Helper function to detect network connectivity issues
  const isNetworkError = (error: any): boolean => {
    // Always check navigator.onLine first - most reliable indicator
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      console.log('Network error detected: navigator.onLine is false');
      return true;
    }
    
    // Check for common network error patterns
    if (error && typeof error === 'object') {
      const errorMessage = error.message?.toLowerCase() || '';
      const errorName = error.name?.toLowerCase() || '';
      const errorString = error.toString?.()?.toLowerCase() || '';
      
      // Log the error for debugging
      console.log('Checking error for network issues:', {
        message: errorMessage,
        name: errorName,
        status: error.status,
        code: error.code,
        type: error.type,
        fullError: error
      });
      
      // Check various network error indicators
      const networkKeywords = [
        'network', 'fetch', 'connection', 'timeout', 'offline', 'unreachable',
        'cors', 'net::', 'failed to fetch', 'load failed', 'network request failed',
        'connection refused', 'connection reset', 'no internet', 'dns'
      ];
      
      const hasNetworkKeyword = networkKeywords.some(keyword => 
        errorMessage.includes(keyword) || 
        errorName.includes(keyword) || 
        errorString.includes(keyword)
      );
      
      const isNetworkStatus = (
        error.status === 0 || // No response from server (common for network issues)
        error.status === 408 || // Request timeout
        error.status === 504 || // Gateway timeout
        error.status === 502 || // Bad gateway
        error.status === 503    // Service unavailable
      );
      
      const isNetworkCode = (
        error.code === 'NETWORK_ERROR' ||
        error.code === 'TIMEOUT' ||
        error.code === 'ENOTFOUND' ||
        error.code === 'ECONNREFUSED' ||
        error.code === 'ECONNRESET'
      );
      
      if (hasNetworkKeyword || isNetworkStatus || isNetworkCode) {
        console.log('Network error detected:', { hasNetworkKeyword, isNetworkStatus, isNetworkCode });
        return true;
      }
    }
    
    // If error is a simple string, check for network keywords
    if (typeof error === 'string') {
      const errorLower = error.toLowerCase();
      if (errorLower.includes('network') || errorLower.includes('connection') || errorLower.includes('fetch')) {
        console.log('Network error detected in string:', error);
        return true;
      }
    }
    
    return false;
  };

  const getNetworkErrorMessage = (): string => {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      return 'Network connection lost. Please check your internet connection and try again.';
    }
    return 'Network error occurred during upload. Please check your connection and retry.';
  };

  // Helper function to create user-friendly error messages for file rejections
  const getFileRejectionMessage = (rejections: FileRejection[]): { title: string; details: string } => {
    if (rejections.length === 0) return { title: '', details: '' };

    // Check the rejection reasons
    const hasInvalidType = rejections.some(r => r.errors.some(e => e.code === 'file-invalid-type'));
    const hasLargeFile = rejections.some(r => r.errors.some(e => e.code === 'file-too-large'));
    
    let title = '';
    let details = '';

    if (hasInvalidType && hasLargeFile) {
      title = 'Invalid files detected. Please check file type and size.';
    } else if (hasInvalidType) {
      title = 'Invalid file type. Please upload only .yaml or .yml files.';
    } else if (hasLargeFile) {
      title = `File too large. Maximum size is ${Math.floor(maxSize / (1024 * 1024))}MB per file.`;
    } else {
      title = 'File upload rejected. Please check your files.';
    }

    // Create details message
    if (rejections.length === 1) {
      details = `File rejected: ${rejections[0].file.name}`;
    } else {
      const fileNames = rejections.map(r => r.file.name).slice(0, 3);
      details = `${rejections.length} files rejected: ${fileNames.join(', ')}${rejections.length > 3 ? '...' : ''}`;
    }

    return { title, details };
  };

  useEffect(() => {
    if (uploadingFiles.length === 0) {
      setAllUploadsComplete(false);
    }
  });

  useEffect(() => {
    let newState: 'IDLE' | 'UPLOADING' | 'COMPLETED' = 'IDLE';

    if (uploadingFiles.length > 0) {
      const activeFiles = uploadingFiles.filter(f => f.status !== 'error');
      const errorFiles = uploadingFiles.filter(f => f.status === 'error');
      
      // Only check for network errors if there are actual upload errors and no file rejection errors are being shown
      // This prevents showing network error when the issue is just wrong file type/extension
      if (errorFiles.length > 0 && !showNetworkError && !showFileRejectionError) {
        // Check if navigator is offline
        if (typeof navigator !== 'undefined' && navigator.onLine === false) {
          console.log('Network error detected in useEffect: navigator.onLine is false');
          setNetworkErrorMessage(getNetworkErrorMessage());
          setShowNetworkError(true);
        }
      }
      
      if (activeFiles.length > 0 && activeFiles.every(f => f.status === 'completed')) {
        newState = 'COMPLETED';
        setAllUploadsComplete(true);
      } else {
        newState = 'UPLOADING';
      }
    }

    setUploadState(newState);
    onUploadStateChange?.(newState);
  }, [uploadingFiles, onUploadStateChange, showNetworkError, showFileRejectionError]);

  const simulateFileUploadWithProcessCreation = async (files: File[]) => {
    console.log("Starting process creation for files:", files.map(f => f.name));
    
    // Add all files to UI immediately
    const newFiles: UploadingFile[] = files.map(file => ({
      file,
      progress: 0,
      status: 'uploading',
      id: uuidv4(),
      batchId: '' // Will be set after process creation
    }));

    setUploadingFiles(prev => [...prev, ...newFiles]);

    // Declare interval IDs in outer scope so they can be accessed in catch block
    let createIntervalId: ReturnType<typeof setInterval> | undefined;
    let uploadIntervalId: ReturnType<typeof setInterval> | undefined;

    try {
      // Step 1: Slow progress for create process call (0% to 50%)
      console.log("Creating new process...");
      const createDuration = 4000; // 4 seconds for create process (slower)
      const createSteps = 30;
      const createIncrement = 50 / createSteps; // Progress to 50%
      const createStepDuration = createDuration / createSteps;

      let currentProgress = 0;
      
      // Start create process progress
      createIntervalId = setInterval(() => {
        currentProgress += createIncrement;
        
        setUploadingFiles(prev =>
          prev.map(f =>
            newFiles.some(nf => nf.id === f.id)
              ? {
                ...f,
                progress: Math.min(currentProgress, 50),
                status: 'uploading'
              }
              : f
          )
        );

        if (currentProgress >= 50) {
          clearInterval(createIntervalId);
        }
      }, createStepDuration);

      // Call create process API
      const processResult = await dispatch(createProcess()).unwrap();
      console.log("Process created successfully:", processResult);
      
      const processId = processResult.process_id;
      setBatchId(processId);
      
      // Update all files with the process ID
      setUploadingFiles(prev =>
        prev.map(f =>
          newFiles.some(nf => nf.id === f.id) ? { ...f, batchId: processId } : f
        )
      );

      // Wait for create progress to reach 50%
      await new Promise(resolve => {
        const checkProgress = () => {
          if (currentProgress >= 50) {
            resolve(undefined);
          } else {
            setTimeout(checkProgress, 100);
          }
        };
        checkProgress();
      });

      // Step 2: Upload files (50% to 75%)
      console.log("Uploading files...");
      const uploadDuration = 3000; // 3 seconds for upload
      const uploadSteps = 20;
      const uploadIncrement = 25 / uploadSteps; // Progress from 50% to 75%
      const uploadStepDuration = uploadDuration / uploadSteps;

      currentProgress = 50; // Start from where create process ended
      
      // Start upload progress
      uploadIntervalId = setInterval(() => {
        currentProgress += uploadIncrement;
        
        setUploadingFiles(prev =>
          prev.map(f =>
            newFiles.some(nf => nf.id === f.id)
              ? {
                ...f,
                progress: Math.min(currentProgress, 75),
                status: 'uploading'
              }
              : f
          )
        );

        if (currentProgress >= 75) {
          clearInterval(uploadIntervalId);
        }
      }, uploadStepDuration);

      // Call upload files API
      try {
        await dispatch(uploadFiles({
          process_id: processId,
          files: files
        })).unwrap();
        console.log('Files uploaded successfully');
        
        // Clear upload interval and set to 100% only on success
        clearInterval(uploadIntervalId);
        
        // Upload completed - set to 100% and mark as completed
        setUploadingFiles(prev =>
          prev.map(f =>
            newFiles.some(nf => nf.id === f.id)
              ? {
                ...f,
                progress: 100,
                status: 'completed'
              }
              : f
          )
        );
        
        // Clear any file rejection errors when files are successfully uploaded
        if (showFileRejectionError) {
          setShowFileRejectionError(false);
          setRejectedFiles([]);
        }
        
        // Files uploaded successfully - user can now click "Start processing" button
        console.log("Files uploaded successfully. User can now click 'Start processing' to begin processing.");
      } catch (uploadError) {
        // Clear upload interval immediately on upload error
        clearInterval(uploadIntervalId);
        
        // Add comprehensive error logging
        console.error('Upload error details:', {
          error: uploadError,
          message: uploadError?.message,
          name: uploadError?.name,
          status: uploadError?.status,
          code: uploadError?.code,
          navigatorOnline: navigator?.onLine
        });
        
        // Check if this is a network error and show network error message
        const isNetworkIssue = isNetworkError(uploadError);
        console.log('Is network error?', isNetworkIssue);
        
        if (isNetworkIssue) {
          setNetworkErrorMessage(getNetworkErrorMessage());
          setShowNetworkError(true);
          console.log('Network error detected - showing MessageBar');
        } else {
          // For now, treat ALL upload errors as potential network issues
          console.log('Treating upload error as potential network issue');
          setNetworkErrorMessage('Upload failed. This might be due to network connectivity issues. Please try again.');
          setShowNetworkError(true);
        }
        
        // Mark files as error
        setUploadingFiles(prev =>
          prev.map(f =>
            newFiles.some(nf => nf.id === f.id) ? { ...f, status: 'error' } : f
          )
        );
        
        throw uploadError; // Re-throw to be caught by outer catch block
      }

    } catch (error) {
      console.error("Failed to create process or upload files:", error);
      // Clear any running intervals when error occurs
      if (createIntervalId) clearInterval(createIntervalId);
      if (uploadIntervalId) clearInterval(uploadIntervalId);
      
      // Check if this is a network error
      if (isNetworkError(error)) {
        setNetworkErrorMessage(getNetworkErrorMessage());
        setShowNetworkError(true);
      }
      
      // Mark all files as error
      setUploadingFiles(prev =>
        prev.map(f =>
          newFiles.some(nf => nf.id === f.id) ? { ...f, status: 'error' } : f
        )
      );
    }
  };

  const uploadAdditionalFilesToExistingProcess = async (files: File[]) => {
    console.log("Uploading additional files to existing process:", batchId, files.map(f => f.name));
    
    // Add all files to UI immediately
    const newFiles: UploadingFile[] = files.map(file => ({
      file,
      progress: 0,
      status: 'uploading',
      id: uuidv4(),
      batchId: batchId
    }));

    setUploadingFiles(prev => [...prev, ...newFiles]);

    // Declare interval ID in outer scope
    let uploadIntervalId: ReturnType<typeof setInterval> | undefined;

    try {
      // Start progress simulation for additional files (0% to 98%)
      console.log("Starting upload of additional files...");
      const uploadDuration = 3000; // 3 seconds for additional uploads
      const uploadSteps = 25;
      const uploadIncrement = 98 / uploadSteps; // Progress to 98%
      const uploadStepDuration = uploadDuration / uploadSteps;

      let currentProgress = 0;
      
      // Start upload progress
      uploadIntervalId = setInterval(() => {
        currentProgress += uploadIncrement;
        
        setUploadingFiles(prev =>
          prev.map(f =>
            newFiles.some(nf => nf.id === f.id)
              ? {
                ...f,
                progress: Math.min(currentProgress, 98),
                status: 'uploading'
              }
              : f
          )
        );

        if (currentProgress >= 98) {
          clearInterval(uploadIntervalId);
        }
      }, uploadStepDuration);

      // Call upload files API with existing process ID and new files
      try {
        await dispatch(uploadFiles({
          process_id: batchId, // Use existing process ID
          files: files
        })).unwrap();
        console.log('Additional files uploaded successfully to process:', batchId);
        
        // Clear interval and set to 100% only on success
        clearInterval(uploadIntervalId);
        
        // Complete the progress to 100%
        setUploadingFiles(prev =>
          prev.map(f =>
            newFiles.some(nf => nf.id === f.id)
              ? {
                ...f,
                progress: 100,
                status: 'completed'
              }
              : f
          )
        );
        
        // Clear any file rejection errors when files are successfully uploaded
        if (showFileRejectionError) {
          setShowFileRejectionError(false);
          setRejectedFiles([]);
        }
      } catch (uploadError) {
        // Clear interval immediately on upload error
        clearInterval(uploadIntervalId);
        
        // Add comprehensive error logging
        console.error('Additional files upload error details:', {
          error: uploadError,
          message: (uploadError as any)?.message,
          name: (uploadError as any)?.name,
          status: (uploadError as any)?.status,
          code: (uploadError as any)?.code,
          navigatorOnline: navigator?.onLine
        });
        
        // Check if this is a network error and show network error message
        const isNetworkIssue = isNetworkError(uploadError);
        console.log('Is network error for additional files?', isNetworkIssue);
        
        if (isNetworkIssue) {
          setNetworkErrorMessage(getNetworkErrorMessage());
          setShowNetworkError(true);
          console.log('Network error detected for additional files - showing MessageBar');
        } else {
          // For now, treat ALL upload errors as potential network issues
          console.log('Treating additional files upload error as potential network issue');
          setNetworkErrorMessage('Upload failed. This might be due to network connectivity issues. Please try again.');
          setShowNetworkError(true);
        }
        
        // Mark files as error
        setUploadingFiles(prev =>
          prev.map(f =>
            newFiles.some(nf => nf.id === f.id) ? { ...f, status: 'error' } : f
          )
        );
        
        throw uploadError; // Re-throw to be caught by outer catch block
      }

    } catch (error) {
      console.error("Failed to upload additional files:", error);
      // Clear interval immediately when error occurs
      if (uploadIntervalId) clearInterval(uploadIntervalId);
      
      // Check if this is a network error
      if (isNetworkError(error)) {
        setNetworkErrorMessage(getNetworkErrorMessage());
        setShowNetworkError(true);
      }
      
      // Mark all new files as error with current progress
      setUploadingFiles(prev =>
        prev.map(f =>
          newFiles.some(nf => nf.id === f.id) ? { ...f, status: 'error' } : f
        )
      );
    }
  };

  const onDrop = useCallback(
    async (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      // Handle file rejections first and return early if only rejected files
      if (fileRejections.length > 0) {
        setRejectedFiles(fileRejections);
        setShowFileRejectionError(true);
        
        // Also call the optional external handler if provided
        if (onFileReject) {
          onFileReject(fileRejections);
        }
        
        // If no files were accepted (all were rejected), return early to prevent any upload attempts
        if (acceptedFiles.length === 0) {
          return;
        }
      }

      // Check current files count and determine how many more can be added
      const remainingSlots = MAX_FILES - uploadingFiles.length;

      if (remainingSlots <= 0) {
        // Already at max files, show dialog
        setShowFileLimitDialog(true);
        return;
      }

      // If more files are dropped than slots available
      if (acceptedFiles.length > remainingSlots) {
        // Take only the first `remainingSlots` files
        const filesToUpload = acceptedFiles.slice(0, remainingSlots);
        
        // If no batch exists yet, create process and upload all files
        if (!batchId) {
          simulateFileUploadWithProcessCreation(filesToUpload);
        } else {
          // If batch exists, upload additional files to existing process
          console.log("Adding files to existing process:", batchId);
          uploadAdditionalFilesToExistingProcess(filesToUpload);
        }
        
        if (onFileUpload) onFileUpload(filesToUpload);
        
        // Show dialog about exceeding limit
        setShowFileLimitDialog(true);
      } else {
        // Normal case - if no batch exists, create process and upload all files
        if (!batchId) {
          simulateFileUploadWithProcessCreation(acceptedFiles);
        } else {
          // If batch exists, upload additional files to existing process
          console.log("Adding files to existing process:", batchId);
          uploadAdditionalFilesToExistingProcess(acceptedFiles);
        }
        
        if (onFileUpload) onFileUpload(acceptedFiles);
      }
    },
    [onFileUpload, onFileReject, uploadingFiles.length, batchId]
  );

  const dropzoneOptions: DropzoneOptions = {
    onDrop,
    noClick: true,
    maxSize,
    accept: acceptedFileTypes,
    //maxFiles: MAX_FILES,
  };

  const { getRootProps, getInputProps, open } = useDropzone(dropzoneOptions);

  const removeFile = (fileId: string) => {
    // Find the file to remove to get its name
    const fileToRemove = uploadingFiles.find((f) => f.id === fileId);
    if (!fileToRemove) {
      console.warn("File not found for removal:", fileId);
      return;
    }

    // Remove from UI immediately for better UX
    setUploadingFiles((prev) => {
      const updatedFiles = prev.filter((f) => f.id !== fileId);
      console.log("Updated uploadingFiles:", updatedFiles);
      return updatedFiles;
    });

    // Clear any running upload interval
    if (uploadIntervals[fileId]) {
      clearInterval(uploadIntervals[fileId]);
      setUploadIntervals((prev) => {
        const { [fileId]: _, ...rest } = prev;
        return rest;
      });
    }

    // Backend deletion using new delete file API if file was uploaded successfully and we have a batch ID
    if (fileToRemove.status === "completed" && batchId) {
      console.log("Deleting file from backend:", fileToRemove.file.name);
      dispatch(deleteFile({ 
        process_id: batchId, 
        filename: fileToRemove.file.name 
      }))
        .unwrap()
        .then((response) => {
          console.log("File deleted successfully from backend:", response);
        })
        .catch((error) => {
          console.error("Failed to delete file from backend:", error);
          // For now, we keep the file removed from UI even if backend deletion fails
          // In a production app, you might want to re-add the file to UI on failure
        });
    } else if (fileToRemove.status === "uploading") {
      console.log("File removed during upload, no backend deletion needed");
    } else if (fileToRemove.status === "error") {
      console.log("Error file removed, no backend deletion needed");
    }
  };

  const cancelAllUploads = useCallback(() => {
    // Clear all upload intervals
    dispatch(deleteBatch({ batchId, headers: null }));

    Object.values(uploadIntervals).forEach(interval => clearInterval(interval));
    setUploadIntervals({});
    setUploadingFiles([]);
    setUploadState('IDLE');
    onUploadStateChange?.('IDLE');
    setShowCancelDialog(false);
    setShowLogoCancelDialog(false);
    setBatchId('');
  }, [uploadIntervals, onUploadStateChange]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Store the original function if it exists
      const originalCancelLogoUploads = (window as any).cancelLogoUploads;

      // Override with our new function that shows the dialog
      (window as any).cancelLogoUploads = () => {
        // Show dialog regardless of upload state
        if (uploadingFiles.length > 0) {  // Only show if there are files
          setShowLogoCancelDialog(true);
        }
      };
      // Cleanup: Restore original function on unmount
      return () => {
        (window as any).cancelLogoUploads = originalCancelLogoUploads;
      };
    }
  }, [uploadingFiles.length]); // Runs when uploadingFiles.length changes

  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Store the original function if it exists
      const originalCancelUploads = (window as any).cancelUploads;

      // Override with our new function that shows the dialog
      (window as any).cancelUploads = () => {
        // Show dialog regardless of upload state
        if (uploadingFiles.length > 0) {  // Only show if there are files
          setShowCancelDialog(true);
        }
      };
      // Cleanup
      return () => {
        (window as any).cancelUploads = originalCancelUploads;
      };
    }
  }, [uploadingFiles.length]);

  // Add network connectivity listeners
  useEffect(() => {
    const handleOnline = () => {
      console.log('Network came back online');
      // Optionally clear network error when connection is restored
      if (showNetworkError) {
        setShowNetworkError(false);
        setNetworkErrorMessage('');
      }
    };

    const handleOffline = () => {
      console.log('Network went offline');
      // Show network error immediately when network goes offline during uploads
      if (uploadingFiles.some(f => f.status === 'uploading')) {
        setNetworkErrorMessage('Network connection lost during upload. Please check your internet connection and retry.');
        setShowNetworkError(true);
        
        // Mark all uploading files as error
        setUploadingFiles(prev =>
          prev.map(f =>
            f.status === 'uploading' ? { ...f, status: 'error' } : f
          )
        );
      }
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);

      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }
  }, [uploadingFiles, showNetworkError]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const originalStartTranslating = (window as any).startTranslating;

      (window as any).startTranslating = async () => {
        if (uploadingFiles.length > 0 && batchId) {
          try {
            console.log('Window.startTranslating called - starting processing for process:', batchId);
            
            // Call the start processing API
            await dispatch(startProcessing({
              process_id: batchId
            })).unwrap();
            
            console.log('Processing started successfully, navigating to processing page');
            navigate(`/process/start/${batchId}`);
            return batchId;
          } catch (error) {
            console.error('Failed to start processing from window.startTranslating:', error);
            return null;
          }
        }
        return null;
      };

      // Cleanup
      return () => {
        (window as any).startTranslating = originalStartTranslating;
      };
    }
  }, [uploadingFiles.length, batchId, dispatch, navigate]);

  const toasterId = "uploader-toast";
  const { dispatchToast } = useToastController(toasterId);

  useEffect(() => {
    if (allUploadsComplete) {
      // Show success toast when uploads are complete
      dispatchToast(
        <Toast>
          <ToastTitle>
            All files uploaded successfully!
          </ToastTitle>
        </Toast>,
        { intent: "success" }
      );
    }
  }, [allUploadsComplete, dispatchToast]);

  // Auto-hide file limit exceeded alert after 5 seconds
  useEffect(() => {
    if (fileLimitExceeded) {
      const timer = setTimeout(() => {
        setFileLimitExceeded(false);
      }, 5000);

      return () => clearTimeout(timer);
    }
  }, [fileLimitExceeded]);

  // Auto-hide file rejection error after 8 seconds
  useEffect(() => {
    if (showFileRejectionError) {
      const timer = setTimeout(() => {
        setShowFileRejectionError(false);
        setRejectedFiles([]);
      }, 5000);

      return () => clearTimeout(timer);
    }
  }, [showFileRejectionError]);


  const handleStartProcessing = () => {
    if (uploadState === 'COMPLETED' && onStartTranslating) {
      onStartTranslating();
    }
  };

  return (
    <div 
      className="upload-container"
      style={{ 
        width: '100%', 
        minWidth: '500px', 
        maxWidth: '900px', 
        margin: '0 auto', 
        padding: '16px', 
        height: '100vh',
        maxHeight: '100vh',
        overflow: 'auto',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-start',
        alignItems: 'center'
      }}
    >
      <ConfirmationDialog
        open={showCancelDialog}
        setOpen={setShowCancelDialog}
        title="Cancel upload?"
        message="If you cancel the upload, all the files and any progress will be deleted."
        onConfirm={cancelAllUploads}
        onCancel={() => setShowCancelDialog(false)}
        confirmText="Cancel upload"
        cancelText="Continue upload"
      />

      <ConfirmationDialog
        open={showLogoCancelDialog}
        setOpen={setShowLogoCancelDialog}
        title="Leave without completing?"
        message="If you leave this page, you'll land on the homepage and lose all progress"
        onConfirm={cancelAllUploads}
        onCancel={() => setShowLogoCancelDialog(false)}
        confirmText="Leave and lose progress"
        cancelText="Continue"
      />
      <ConfirmationDialog
        open={showFileLimitDialog}
        setOpen={setShowFileLimitDialog}
        title="File Limit Exceeded"
        message={`Maximum of ${MAX_FILES} files allowed. Only the first ${MAX_FILES} files were uploaded.`}
        onConfirm={() => setShowFileLimitDialog(false)}
        onCancel={() => setShowFileLimitDialog(false)}
        confirmText="OK"
        cancelText=""
      />

      {uploadingFiles.length === 0 && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '8px',
          textAlign: 'center',
          marginBottom: '70px'
        }}>
          {/* Header - Centered */}
          <div className="text-center" style={{textAlign: 'center' }}>
            <h1 className="text-xl font-semibold" style={{ whiteSpace: 'nowrap', margin: '0 0 5px 0' }}>Container Migration</h1>
            <p className="text-gray-600 max-w-2xl mx-auto" style={{ fontSize: '17px', whiteSpace: 'nowrap', margin: '0' }}>
              Migrate your third party container workloads to{" "}
              <a
                href="https://azure.microsoft.com/en-us/products/kubernetes-service/"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#0078d4', textDecoration: 'none' }}
              >
                Azure AKS
              </a>{" "}
            </p>
          </div>
        </div>
      )}

      {uploadingFiles.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '16px', margin: 0 }}>
            {`Uploading (${uploadingFiles.filter(f => f.status === 'completed').length}/${uploadingFiles.length})`}
          </h2>
        </div>
      )}

      {uploadingFiles.length === 0 ? (
        <div style={{
          maxWidth: '850px',
          width: '100%',
          margin: '0 auto',
          backgroundColor: 'white',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.08)',
          padding: '30px',
          marginBottom: '15px',
          boxSizing: 'border-box'
        }}>
          <h2 style={{ fontSize: '16px', margin: '0 0 15px 0', textAlign: 'left' }}>
            Upload files in batch
          </h2>
          <div
            {...getRootProps()}
            style={{
              width: '100%',
              border: "2px dashed #ccc",
              borderRadius: "4px",
              padding: "60px 80px",
              backgroundColor: '#FAFAFA',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '271px',
              marginBottom: '0',
              boxSizing: 'border-box'
            }}
          >
            <input {...getInputProps()} />
            
            <img
              src="/images/Arrow-Upload.png"
              alt="Upload Icon"
              style={{ width: 64, height: 64 }}
            />
            <p style={{
              margin: '16px 0 0 0',
              fontSize: '18px',
              color: '#333',
              fontWeight: '600'
            }}>
              Drag and drop files here
            </p>
            <p style={{ margin: '8px 0', fontSize: '14px', color: '#666' }}>
              or
            </p>
            <Button
              appearance="secondary"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                open();
              }}
              style={{
                minWidth: '160px',
                height: '48px',
                backgroundColor: 'white',
                border: '1px solid #ccc',
                borderRadius: '4px',
                fontSize: '15px',
                fontWeight: '500',
                padding: '14px 24px'
              }}
            >
              Browse files
            </Button>
            <p style={{
              margin: '20px 0 0 0',
              fontSize: '12px',
              color: '#666'
            }}>
              Limit {Math.floor(maxSize / (1024 * 1024))}MB per file • YAML/YML Only • {MAX_FILES} files max
            </p>
          </div>
          <p style={{
            margin: '18px 0 0 0',
            fontSize: '14px',
            color: '#666',
            textAlign: 'center',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            fontWeight: 'normal'
          }}>
            <img 
              src="/images/lock.png" 
              alt="Lock" 
              style={{
                width: '16px',
                height: '16px',
                animation: 'lockPulse 2s ease-in-out infinite',
                transformOrigin: 'center'
              }}
            /> Your files are stored and not publicly available
          </p>
        </div>
      ) : (
        <div
          {...getRootProps()}
          style={{
            width: '95%',
            border: "2px dashed #ccc",
            borderRadius: "4px",
            padding: "20px",
            backgroundColor: '#FAFAFA',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: '80px',
            marginBottom: '16px',
          }}
        >
          <input {...getInputProps()} />
          
          {uploadingFiles.length > 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <img
                  src="/images/Arrow-Upload.png"
                  alt="Upload Icon"
                  style={{ width: 32, height: 32 }}
                />
                <div>
                  <p style={{
                    margin: '0',
                    fontSize: '16px',
                    color: '#333'
                  }}>
                    Drag and drop files here
                  </p>
                  <p style={{
                    margin: '4px 0 0 0',
                    fontSize: '12px',
                    color: '#666'
                  }}>
                    Limit {Math.floor(maxSize / (1024 * 1024))}MB per file • YAML/YML Only • {uploadingFiles.length}/{MAX_FILES} files
                  </p>
                </div>
              </div>
              <Button
                appearance="secondary"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  open();
                }}
                style={{
                  minWidth: '120px',
                  backgroundColor: 'white',
                  border: '1px solid grey',
                  borderRadius: '4px',
                  height: '32px'
                }}
              >
                Browse files
              </Button>
            </>
          ) : (
            <>
              <img
                src="/images/Arrow-Upload.png"
                alt="Upload Icon"
                style={{ width: 64, height: 64 }}
              />
              <p style={{
                margin: '16px 0 0 0',
                fontSize: '18px',
                color: '#333',
                fontWeight: '600'
              }}>
                Drag and drop files here
              </p>
              <p style={{ margin: '8px 0', fontSize: '14px', color: '#666' }}>
                or
              </p>
              <Button
                appearance="secondary"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  open();
                }}
                style={{
                  minWidth: '120px',
                  backgroundColor: 'white',
                  border: '1px solid grey',
                  borderRadius: '4px',
                }}
              >
                Browse files
              </Button>
              <p style={{
                margin: '8px 0 0 0',
                fontSize: '12px',
                color: '#666'
              }}>
                Limit {Math.floor(maxSize / (1024 * 1024))}MB per file • YAML/YML Only • {MAX_FILES} files max
              </p>
            </>
          )}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '13px', width: '100%', maxWidth: '900px', paddingBottom: 10, borderRadius: '4px', margin: '0 auto' }}>
        {allUploadsComplete && (
          <MessageBar
            messageBarType={MessageBarType.success}
            isMultiline={false}
            styles={{
              root: { display: "flex", alignItems: "left" }, // Align the icon and text
              icon: { display: "none" },
            }}
          >
            <div style={{ display: "flex", alignItems: "left" }}>
              <CircleCheck
                strokeWidth="2.5px"
                color="#37a04c"
                size="16px" // Slightly larger for better balance
                style={{ marginRight: "8px" }}
              />
              <span>All valid files uploaded successfully!</span>
            </div>
          </MessageBar>
        )}

        {fileLimitExceeded && (
          <MessageBar
            messageBarType={MessageBarType.warning}
            isMultiline={false}
            onDismiss={() => setFileLimitExceeded(false)}
            dismissButtonAriaLabel="Close"
            styles={{
              root: { display: "flex", alignItems: "center" },
            }}
          >
            <X
              strokeWidth="2.5px"
              color='#d83b01'
              size='14px'
              style={{ marginRight: "12px", paddingTop: 3 }}
            />
            Maximum of {MAX_FILES} files allowed. Some files were not uploaded.
          </MessageBar>
        )}

        {showFileRejectionError && rejectedFiles.length > 0 && (() => {
          const errorMessages = getFileRejectionMessage(rejectedFiles);
          return (
            <div style={{ width: '100%', display: 'flex' }}>
              <MessageBar
                messageBarType={MessageBarType.error}
                isMultiline={false}
                onDismiss={() => {
                  setShowFileRejectionError(false);
                  setRejectedFiles([]);
                }}
                dismissButtonAriaLabel="Close"
                styles={{
                  root: { display: "flex", alignItems: "flex-start", width: "100% !important" },
                  icon: { display: "none" },
                }}
                style={{ flex: 1, width: "100% !important" }}
              >
                <div>
                <CircleX
                strokeWidth="2.5px"
                color="#f80808ff"
                size="16px" // Slightly larger for better balance
                style={{ marginRight: "8px" }}
              />
              <span>{errorMessages.title} {errorMessages.details}</span>
              </div>
                {/* <div>
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                    {errorMessages.title} {errorMessages.details}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>
                    {errorMessages.details}
                  </div>
                </div> */}
              </MessageBar>
            </div>
          );
        })()}

        {showNetworkError && (
          <div style={{ width: '100%', display: 'flex' }}>
            <MessageBar
              messageBarType={MessageBarType.error}
              isMultiline={false}
              onDismiss={() => {
                setShowNetworkError(false);
                setNetworkErrorMessage('');
              }}
              dismissButtonAriaLabel="Close"
              styles={{
                root: { display: "flex", alignItems: "flex-start", width: "100% !important" },
                icon: { display: "none" },
              }}
              style={{ flex: 1, width: "100% !important" }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <CircleX
                    strokeWidth="2.5px"
                    color="#f80808ff"
                    size="16px"
                    style={{ marginRight: "8px" }}
                  />
                  <span>{networkErrorMessage}</span>
                </div>
              </div>
            </MessageBar>
          </div>
        )}
      </div>

      {uploadingFiles.length > 0 && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          width: '100%',
          maxHeight: '300px',
          overflowY: 'auto',
          scrollbarWidth: 'thin'
        }}>
          {uploadingFiles.map((file) => (
            <div
              key={file.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '8px 12px',
                backgroundColor: 'white',
                borderRadius: '4px',
                border: '1px solid #eee',
                width: 'auto',
                maxWidth: '1200px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', width: '24px' }}>
                📄
              </div>
              <Tooltip content={file.file.name} relationship="label">
                <div
                  style={{
                    width: 80,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    fontSize: "14px",
                    alignItems: "left",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  {file.file.name}
                </div>
              </Tooltip>
              <div style={{
                flex: 1,
                height: '4px',
                backgroundColor: '#eee',
                borderRadius: '2px',
                overflow: 'hidden'
              }}>
                <div
                  style={{
                    width: `${file.progress}%`,
                    height: '100%',
                    backgroundColor: file.status === 'error' ? '#ff4444' :
                      file.status === 'completed' ? '#4CAF50' :
                        '#2196F3',
                    transition: 'width 0.3s ease'
                  }}
                />
              </div>
              <Tooltip content="Remove file" relationship="label">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(file.id);
                  }}
                  style={{
                    border: 'none',
                    background: 'none',
                    cursor: 'pointer',
                    padding: '4px',
                    color: '#666',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '24px',
                    height: '24px'
                  }}
                >
                  ✕
                </button>
              </Tooltip>
            </div>
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: '16px',
        marginTop: '15px'
      }}>
        <Button
          appearance="secondary"
          onClick={() => {
            if (window.cancelUploads) {
              window.cancelUploads();
            }
          }}
          disabled={uploadState === 'IDLE'}
          style={{
            minWidth: '100px',
            height: '40px',
            fontSize: '16px'
          }}
        >
          Cancel
        </Button>
        
        <Button
          appearance="primary"
          onClick={async () => {
            // Start processing when user clicks the button
            if (uploadState === 'COMPLETED' && batchId) {
              try {
                console.log("User clicked 'Start processing', calling API for process:", batchId);
                
                // Call the start processing API
                await dispatch(startProcessing({
                  process_id: batchId
                })).unwrap();
                
                console.log("Processing started successfully, navigating to:", `/process/start/${batchId}`);
                navigate(`/process/start/${batchId}`);
              } catch (error) {
                console.error("Failed to start processing:", error);
                // TODO: Show error message to user
              }
            } else {
              console.log("Cannot start processing - uploadState:", uploadState, "batchId:", batchId);
            }
          }}
          disabled={uploadState !== 'COMPLETED'}
          style={{
            minWidth: '160px',
            height: '40px',
            fontSize: '16px'
          }}
        >
          Start processing
        </Button>
      </div>
    </div>
  );
};

export default FileUploadZone;