import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { apiService } from '../services/ApiService';

// Interface for the migration status render response
interface MigrationRenderResponse {
  process_id: string;
  phase: 'Documentation' | 'Analysis' | 'Design' | 'YAML';
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  step: string;
  last_update_time: string;
  started_at_time: string;
  agents: string[];
  failure_reason?: string;
  failure_details?: string;
  failure_step?: string;
  failure_agent?: string;
  failure_timestamp?: string;
  stack_trace?: string;
  health_status: '🟢 STABLE' | '🟡 WARNING' | '🔴 CRITICAL';
  active_agent_count: number;
  total_agents: number;
  bottleneck_score?: number;
  fast_agents?: string[];
  failed_agents?: string[];
}

// Interface for the file upload response  
interface FileUploadResponse {
  message: string;
  user_id: string;
  process_id: string;
  files: Array<{
    filename: string;
    content_type: string;
    size: number;
  }>;
}

// Interface for the start processing response  
interface StartProcessingResponse {
  message: string;
  process_id: string;
  user_id: string;
  status: string;
}

// Interface for the process start response (old endpoint)
interface ProcessStartResponse {
  user_id: string;
  process_id: string;
  message: string;
  files: Array<{
    filename: string;
    content_type: string;
    size: number;
  }>;
}

/*
 * AKS Migration File Upload Workflow
 * 
 * This file implements the required workflow for the AKS Migration backend API:
 * 
 * 1. Create Process: Call /api/process/create to get a unique process ID
 * 2. Upload Files: Call /api/process/start with process_id and files
 * 3. Check Status: Use /api/process/status/{process_id}/render/ to monitor progress
 * 
 * API Endpoints:
 * - POST /api/process/create -> Returns: { "id": "process-uuid" }
 * - POST /api/process/start -> Returns: { 
 *     "user_id": "user@domain.com", 
 *     "process_id": "process-uuid", 
 *     "message": "Files uploaded successfully",
 *     "files": [{ "filename": "file.yaml", "content_type": "application/x-yaml", "size": 1024 }]
 *   }
 * - GET /api/process/status/{process_id}/render/ -> Returns: Migration status with agents and progress info
 *   {
 *     "process_id": "uuid",
 *     "phase": "Documentation|Analysis|Design|YAML",
 *     "status": "pending|in_progress|completed|failed", 
 *     "step": "current step name",
 *     "last_update_time": "timestamp",
 *     "started_at_time": "timestamp", 
 *     "agents": ["agent status strings"],
 *     "health_status": "🟢 STABLE|🟡 WARNING|🔴 CRITICAL",
 *     "active_agent_count": number,
 *     "total_agents": number
 *   }
 * 
 * ⚠️ Important: Always call /create first, then /start with the received process ID
 * You can call /start multiple times with the same process ID to upload files in batches
 */

// API call to create a new Process record
export const createProcess = createAsyncThunk<
  { process_id: string }, // Return type - object with process_id property (based on API spec)
  void, // No parameters
  { rejectValue: string } // Type for rejectWithValue
>(
  'process/create',
  async (_, { rejectWithValue }) => {
    try {
      console.log("Creating new process...");
      console.log("Making request to: /process/create");
      
      const response = await apiService.post('/process/create', {});
      console.log("Process creation response:", response);
      return response;
    } catch (error: any) {
      console.error("Process creation error:", error);
      return rejectWithValue(error.message || 'Failed to create process');
    }
  }
);

// Dummy API call for batch deletion
export const deleteBatch = createAsyncThunk<
  any, // The type of returned response data (can be updated to match API response)
  { batchId: string; headers?: Record<string, string> | null }, // Payload type
  { rejectValue: string } // Type for rejectWithValue
>(
  'batch/deleteBatch',
  async ({ batchId, headers }: { batchId: string; headers?: Record<string, string> | null }, { rejectWithValue }) => {
    try {
      const response = await apiService.delete(`/process/delete-process/${batchId}`, null); // Pass null as body
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to delete process');
    }
  }
);

export const deleteFileFromBatch = createAsyncThunk(
  'batch/deleteFileFromBatch',
  async (fileId: string, { rejectWithValue }) => {
    try {
      const response = await apiService.delete(`/delete-file/${fileId}`, null); // Pass null as body

      // Return the response data
      return response;
    } catch (error) {
      // Handle the error
      return rejectWithValue(error.response?.data || 'Failed to delete batch');
    }
  }
);

// API call for uploading single file in batch
export const uploadFile = createAsyncThunk('file/upload', // Updated action name
  async (payload: { file: File; batchId: string }, { rejectWithValue }) => {
    try {
      console.log("uploadFile called with payload:", { fileName: payload.file.name, batchId: payload.batchId });
      
      const formData = new FormData();

      // Append process_id (changed from batchId to match new API)
      formData.append("process_id", payload.batchId);
      console.log("Added process_id to FormData:", payload.batchId);

      // Append the single file (changed field name from 'file' to 'files' to match new API)
      formData.append("files", payload.file);
      console.log("Added file to FormData:", payload.file.name);

      console.log("Making request to: /process/start");
      
      const response = await apiService.upload('/process/start', formData);
      return response;
    } catch (error) {
      console.error("Upload error:", error);
      return rejectWithValue(error.response?.data || 'Failed to upload file');
    }
  }
);



// Type definitions for the new API response structure
interface FileUploadInfo {
  filename: string;
  content_type: string;
  size: number;
}

interface ProcessStartResponse {
  user_id: string;
  process_id: string;
  message: string;
  files: FileUploadInfo[];
}

interface FileState {
  batchId: string | null;
  fileList: { fileId: string; originalName: string }[]; // Store file_id & name
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

// Initial state
const initialFileState: FileState = {
  batchId: null,
  fileList: [],
  status: 'idle',
  error: null,
};

const fileSlice = createSlice({
  name: 'fileUpload',
  initialState: initialFileState,
  reducers: {
    resetState: (state) => {
      state.batchId = null;
      state.fileList = [];
      state.status = 'idle';
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(uploadFile.fulfilled, (state, action: PayloadAction<ProcessStartResponse>) => {
        // Updated to match new API response structure
        state.batchId = action.payload.process_id; // Store process ID from new API
        
        // Add files from the response to the file list
        action.payload.files.forEach(file => {
          state.fileList.push({
            fileId: `${file.filename}_${Date.now()}`, // Use filename + timestamp as ID
            originalName: file.filename, // Now we have the actual filename
          });
        });
        
        state.status = 'succeeded';
      })
      .addCase(uploadFile.rejected, (state, action: PayloadAction<any>) => {
        state.error = action.payload;
        state.status = 'failed';
      })
      .addCase(deleteFileFromBatch.fulfilled, (state, action) => {
        state.fileList = state.fileList.filter(file => file.fileId !== action.meta.arg);
      });
  },
});


//API call for File Deletion (New File Management Feature)
export const deleteFile = createAsyncThunk(
  "process/delete-file",
  async (payload: { process_id: string; filename: string }, { rejectWithValue }) => {
    try {
      console.log("Deleting file:", payload.filename, "from process:", payload.process_id);
      
      // Create FormData with process_id as required by backend API
      const formData = new FormData();
      formData.append('process_id', payload.process_id);
      
      console.log("Making delete request to: /process/delete-file/" + encodeURIComponent(payload.filename));
      
      const response = await apiService.delete(`/process/delete-file/${encodeURIComponent(payload.filename)}`, formData);

      console.log("Delete file response:", response);
      
      return response;
    } catch (error: any) {
      console.error("Delete file error:", error);
      if (error.response?.status === 404) {
        console.warn("File not found for deletion:", payload.filename);
      }
      return rejectWithValue(error.response?.data || 'Failed to delete file');
    }
  }
);

//API call for File Upload (New Two-Step Workflow)
export const uploadFiles = createAsyncThunk(
  "process/upload",
  async (payload: { process_id: string; files: File[] }, { rejectWithValue }) => {
    try {
      console.log("Uploading files to process:", payload.process_id, "files:", payload.files.map(f => f.name));
      
      // Create FormData for file upload
      const formData = new FormData();
      
      // Add process_id to the FormData
      formData.append('process_id', payload.process_id);
      
      // Add all files with the same field name 'files'
      payload.files.forEach(file => {
        formData.append('files', file);
      });
      
      console.log("Making upload request to: /process/upload");
      
      const response = await apiService.upload('/process/upload', formData);

      console.log("Upload response:", response);
      
      return response;
    } catch (error: any) {
      console.error("Upload error:", error);
      if (error.response?.status === 410) {
        // Handle deprecated endpoint
        console.warn("Upload endpoint deprecated, falling back to old workflow");
      }
      return rejectWithValue(error.response?.data || 'Failed to upload files');
    }
  }
);

//API call for Start Processing (New Two-Step Workflow)
export const startProcessing = createAsyncThunk(
  "process/start-processing",
  async (payload: { process_id: string }, { rejectWithValue }) => {
    try {
      console.log("Starting processing for process:", payload.process_id);
      
      // Create FormData for start processing
      const formData = new FormData();
      formData.append('process_id', payload.process_id);
      
      console.log("Making start processing request to: /process/start-processing");
      
      const response = await apiService.upload('/process/start-processing', formData);

      console.log("Start processing response:", response);
      
      return response;
    } catch (error: any) {
      console.error("Start processing error:", error);
      if (error.response?.status === 410) {
        // Handle deprecated endpoint
        console.warn("Start processing endpoint deprecated");
      }
      return rejectWithValue(error.response?.data || 'Failed to start processing');
    }
  }
);

//API call for Batch Start Processing (DEPRECATED - File Upload)
export const startProcessingOld = createAsyncThunk(
  "process/start",
  async (payload: { process_id: string; files: File[] }, { rejectWithValue }) => {
    try {
      console.log("Starting process with files:", payload.files.map(f => f.name));
      
      // Create FormData for file upload
      const formData = new FormData();
      
      // Add process_id to the FormData
      formData.append('process_id', payload.process_id);
      
      // Add all files with the same field name 'files' (updated to match new API)
      payload.files.forEach(file => {
        formData.append('files', file);
      });
      
      console.log("Making request to: /process/start");
      
      const response = await apiService.upload('/process/start', formData);

      console.log("Process start response:", response);

      return response;
    } catch (error) {
      console.error("Process start error:", error);
      console.error("Error response:", error.response?.data);
      return rejectWithValue(error.response?.data || "Failed to start processing");
    }
  }
);

// API call to check migration status
export const checkMigrationStatus = createAsyncThunk<
  MigrationRenderResponse, // Response type
  { processId: string }, // Payload type
  { rejectValue: string } // Type for rejectWithValue
>(
  'process/status',
  async ({ processId }, { rejectWithValue }) => {
    try {
      console.log("Checking migration status for process:", processId);
      console.log("Making request to: /process/status/" + processId + "/render/");
      
      const response = await apiService.get(`/process/status/${processId}/render/`);
      console.log("Migration status response:", response);
      return response;
    } catch (error: any) {
      console.error("Migration status check error:", error);
      console.error("Error response:", error.response?.data);
      return rejectWithValue(error.response?.data || 'Failed to check migration status');
    }
  }
);

// Helper function for checking status with navigation callback
export const checkMigrationStatusWithNavigation = createAsyncThunk<
  { status: MigrationRenderResponse; shouldNavigate: boolean }, // Return type
  { processId: string; onComplete?: (processId: string) => void }, // Payload type  
  { rejectValue: string } // Type for rejectWithValue
>(
  'process/statusWithNavigation',
  async ({ processId, onComplete }, { rejectWithValue }) => {
    try {
      console.log("Checking migration status with navigation for process:", processId);
      
      const response = await apiService.get(`/process/status/${processId}/render/`);
      
      const statusData: MigrationRenderResponse = response;
      console.log("Migration status response:", statusData);
      
      // Check if migration is completed and trigger navigation
      const shouldNavigate = statusData.status === 'completed';
      if (shouldNavigate && onComplete) {
        console.log("Migration completed, triggering navigation callback");
        onComplete(processId);
      }
      
      return { status: statusData, shouldNavigate };
    } catch (error: any) {
      console.error("Migration status check error:", error);
      return rejectWithValue(error.response?.data || 'Failed to check migration status');
    }
  }
);

interface FetchBatchHistoryPayload {
  headers?: Record<string, string>;
}

// Async thunk to fetch batch history with headers
export const fetchBatchHistory = createAsyncThunk(
  "batch/fetchBatchHistory",
  async ({ headers }: FetchBatchHistoryPayload, { rejectWithValue }) => {
    try {
      const response = await apiService.get('/batch-history');
      return response;
    } catch (error) {
      if (error.response && error.response.status === 404) {
        return [];
      }
      return rejectWithValue(error.response?.data || "Failed to load batch history");
    }
  }
);

export const deleteAllBatches = createAsyncThunk(
  "batch/deleteAllBatches",
  async ({ headers }: { headers: Record<string, string> }, { rejectWithValue }) => {
    try {
      const response = await apiService.delete('/delete_all', null); // Pass null as body since no body needed
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || "Failed to delete all batch history");
    }
  }
);

//

// Initial state for the batch slice
const initialState: {
  batches: string[],
  batchId: string | null;
  fileId: string | null;
  message: string;
  loading: boolean;
  error: string | null;
  uploadingFiles: boolean;
  processStatus: string | null; // For processing status from start-processing endpoint
  migrationStatus: MigrationRenderResponse | null; // Properly typed migration status
  statusLoading: boolean; // For status checking loading state
  files: {
    file_id: string;
    batch_id: string;
    original_name: string;
    blob_path: string;
    translated_path: string;
    status: string;
    error_count: number;
    created_at: string;
    updated_at: string;
  }[];
} = {
  batchId: null,
  fileId: null,
  message: '',
  loading: false,
  error: null,
  uploadingFiles: false,
  processStatus: null,
  migrationStatus: null,
  statusLoading: false,
  files: [],
  batches: []
};

export const batchSlice = createSlice({
  name: 'batch',
  initialState,
  reducers: {
    resetBatch: (state) => {
      state.batchId = null;
      state.fileId = null;
      state.message = '';
      state.error = null;
      state.migrationStatus = null; // Reset migration status
      state.statusLoading = false; // Reset status loading
    },
  },
  extraReducers: (builder) => {
    // Handle the createProcess action
    builder
      .addCase(createProcess.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(createProcess.fulfilled, (state, action) => {
        state.loading = false;
        if (action.payload && action.payload.process_id) {
          state.batchId = action.payload.process_id;
          state.message = 'Process created successfully';
        } else {
          state.error = "Unexpected response: Process ID not found.";
        }
      })
      .addCase(createProcess.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
    // Handle the deleteBatch action
    builder
      .addCase(deleteBatch.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(deleteBatch.fulfilled, (state, action) => {
        state.loading = false;
        if (action.payload) {
          state.batchId = action.payload.batch_id;
          state.message = action.payload.message;
        } else {
          state.error = "Unexpected response: Payload is undefined.";
        }
      })
      .addCase(deleteBatch.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
    //delete file from batch
    builder
      .addCase(deleteFileFromBatch.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(deleteFileFromBatch.fulfilled, (state, action) => {
        state.loading = false;
        //state.files = state.files.filter(file => file.file_id !== action.payload.fileId);
        if (action.payload) {
          state.fileId = action.payload.file_id;
          state.message = action.payload.message;
        } else {
          state.error = "Unexpected response: Payload is undefined.";
        }
      })
      .addCase(deleteFileFromBatch.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
    // Handle the uploadFilesInBatch action
    builder
      .addCase(uploadFile.pending, (state) => {
        state.uploadingFiles = true;
        state.error = null;
      })
      .addCase(uploadFile.fulfilled, (state, action) => {
        state.uploadingFiles = false;
        if (action.payload) {
          // Updated to match new API response structure  
          const response = action.payload as ProcessStartResponse;
          state.batchId = response.process_id; // Process ID from new API
          state.message = response.message; // Message from API response

          // Ensure files array exists before pushing
          if (!state.files) {
            state.files = [];
          }

          // Add file information from the new API response
          response.files.forEach(fileInfo => {
            // Create a file object compatible with existing structure
            const fileRecord = {
              file_id: `${fileInfo.filename}_${Date.now()}`, // Generate ID from filename
              batch_id: response.process_id, // Use process_id as batch_id
              original_name: fileInfo.filename,
              blob_path: '', // Not provided by API, will be empty
              translated_path: '', // Not provided by API, will be empty
              status: 'uploaded', // Set initial status
              error_count: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            };
            state.files.push(fileRecord);
          });

          console.log("Upload response (new API format):", response);
          console.log(`Added ${response.files.length} files to state`);
        } else {
          state.error = "Unexpected response: Payload is undefined.";
        }
      })
      .addCase(uploadFile.rejected, (state, action) => {
        state.uploadingFiles = false;
        state.error = action.payload as string;
      });
    //Delete File Action Handle (New File Management Feature)
    builder
      .addCase(deleteFile.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(deleteFile.fulfilled, (state, action) => {
        state.loading = false;
        if (action.payload) {
          const response = action.payload as FileUploadResponse;
          console.log("Delete File Response:", response);
          
          state.message = response.message;
          
          // Update files array with the updated file list from server
          if (response.files) {
            // Replace entire files array with the authoritative server response
            state.files = response.files.map(fileInfo => ({
              file_id: `${fileInfo.filename}_${Date.now()}`,
              batch_id: response.process_id,
              original_name: fileInfo.filename,
              blob_path: '',
              translated_path: '',
              status: 'uploaded',
              error_count: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }));
            
            console.log(`Updated files list after deletion. Current count: ${response.files.length}`);
          }
        } else {
          state.error = "Unexpected response: Payload is undefined.";
        }
      })
      .addCase(deleteFile.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
    //Upload Files Action Handle (New Two-Step Workflow)
    builder
      .addCase(uploadFiles.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(uploadFiles.fulfilled, (state, action) => {
        state.loading = false;
        if (action.payload) {
          const response = action.payload as FileUploadResponse;
          console.log("Upload Files Response:", response);
          
          state.batchId = response.process_id;
          state.message = response.message;
          
          // Update files array with the complete file list from server (cumulative tracking)
          if (response.files && response.files.length > 0) {
            // Replace entire files array with the authoritative server response
            // This ensures we have the complete, up-to-date list of all files
            state.files = response.files.map(fileInfo => ({
              file_id: `${fileInfo.filename}_${Date.now()}`,
              batch_id: response.process_id,
              original_name: fileInfo.filename,
              blob_path: '',
              translated_path: '',
              status: 'uploaded',
              error_count: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }));
            
            console.log(`Updated files list from uploadFiles. Total count: ${response.files.length}`);
          }
        } else {
          state.error = "Unexpected response: Payload is undefined.";
        }
      })
      .addCase(uploadFiles.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
    //Start Processing Action Handle (New Two-Step Workflow)
    builder
      .addCase(startProcessing.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(startProcessing.fulfilled, (state, action) => {
        state.loading = false;
        if (action.payload) {
          const response = action.payload as StartProcessingResponse;
          console.log("Start Processing Response:", response);
          
          state.batchId = response.process_id;
          state.message = response.message;
          state.processStatus = response.status; // Store the processing status
        } else {
          state.error = "Unexpected response: Payload is undefined.";
        }
      })
      .addCase(startProcessing.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
    //Fetch Batch History Action Handle
    builder
      .addCase(fetchBatchHistory.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchBatchHistory.fulfilled, (state, action) => {
        state.loading = false;
        state.batches = action.payload;
      })
      .addCase(fetchBatchHistory.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string | null;
      });
    builder
      .addCase(deleteAllBatches.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(deleteAllBatches.fulfilled, (state) => {
        state.loading = false;
        state.batches = [];
      })
      .addCase(deleteAllBatches.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string | null;
      });
    // Handle the checkMigrationStatus action
    builder
      .addCase(checkMigrationStatus.pending, (state) => {
        state.statusLoading = true;
        state.error = null;
      })
      .addCase(checkMigrationStatus.fulfilled, (state, action) => {
        state.statusLoading = false;
        state.migrationStatus = action.payload;
      })
      .addCase(checkMigrationStatus.rejected, (state, action) => {
        state.statusLoading = false;
        state.error = action.payload as string;
      });
    // Handle the checkMigrationStatusWithNavigation action
    builder
      .addCase(checkMigrationStatusWithNavigation.pending, (state) => {
        state.statusLoading = true;
        state.error = null;
      })
      .addCase(checkMigrationStatusWithNavigation.fulfilled, (state, action) => {
        state.statusLoading = false;
        state.migrationStatus = action.payload.status;
        // Note: Navigation is handled in the action itself via callback
      })
      .addCase(checkMigrationStatusWithNavigation.rejected, (state, action) => {
        state.statusLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { resetBatch } = batchSlice.actions;
export const batchReducer = batchSlice.reducer;
export const fileReducer = fileSlice.reducer;
export const { resetState } = fileSlice.actions;

// Export the migration status interfaces for use in components
export type { MigrationRenderResponse, ProcessStartResponse };

// Helper function for the complete upload workflow (create process + upload files)
export const createProcessAndUploadFiles = createAsyncThunk(
  'process/createAndUpload',
  async (files: File[], { dispatch, rejectWithValue }) => {
    try {
      console.log("Starting complete upload workflow for files:", files.map(f => f.name));
      
      // Step 1: Create process
      const processResult = await dispatch(createProcess()).unwrap();
      const processId = processResult.process_id;
      
      // Step 2: Upload files to the process
      const uploadResult = await dispatch(uploadFiles({ 
        process_id: processId, 
        files: files 
      })).unwrap();
      
      // Step 3: Start processing
      const processingResult = await dispatch(startProcessing({ 
        process_id: processId
      })).unwrap();
      
      const uploadResponse = uploadResult as FileUploadResponse;
      const processingResponse = processingResult as StartProcessingResponse;
      
      return {
        processId: processId,
        uploadResult: uploadResponse,
        processingResult: processingResponse,
        filesUploaded: uploadResponse.files.length,
        uploadedFiles: uploadResponse.files
      };
    } catch (error) {
      console.error("Complete upload workflow failed:", error);
      return rejectWithValue(error);
    }
  }
);