import axios from 'axios';
import { getApiUrl, headerBuilder } from './config';

/*
 * AKS Migration Upload Service
 * 
 * This service implements the required workflow for the AKS Migration backend API:
 * 1. Create Process -> 2. Upload Files -> 3. Check Status
 * 
 * Updated for new API endpoints and response structure:
 * - POST /api/process/create
 * - POST /api/process/start -> Returns detailed file information
 * - GET /api/process/status/{process_id}/render/
 */

// Type definitions for API responses
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

// Updated to follow the new API workflow: create process first, then upload files
export const uploadFiles = async (files: File[], processId?: string): Promise<ProcessStartResponse> => {
  try {
    let currentProcessId = processId;
    
    // If no processId provided, create a new process first
    if (!currentProcessId) {
      console.log("No process ID provided, creating new process...");
      const apiUrl = getApiUrl();
      const createResponse = await axios.post(`${apiUrl}/process/create`, {}, {
        headers: headerBuilder({
          'Content-Type': 'application/json'
        })
      });
      currentProcessId = createResponse.data.id;
      console.log("Created new process with ID:", currentProcessId);
    }

    // Now upload files to the process
    if (!currentProcessId) {
      throw new Error("Failed to get process ID");
    }
    
    const formData = new FormData();
    formData.append('process_id', currentProcessId);
    
    // Add all files with the field name 'files'
    files.forEach(file => {
      formData.append('files', file);
    });
    
    console.log(`Uploading ${files.length} files to process ${currentProcessId}...`);
    
    const apiUrl = getApiUrl();
    const response = await axios.post(`${apiUrl}/process/start`, formData, {
      headers: headerBuilder({
        // Don't set Content-Type - browser sets multipart/form-data automatically
      })
    });
    
    console.log("Upload response:", response.data);
    
    // Type-cast the response to the expected structure
    const uploadResponse = response.data as ProcessStartResponse;
    console.log(`Successfully uploaded ${uploadResponse.files.length} files:`, 
                uploadResponse.files.map(f => f.filename));
    
    return uploadResponse;
    
  } catch (error) {
    console.error("Error in upload workflow:", error);
    throw error;
  }
};

// Function to check migration status
export const checkMigrationStatus = async (processId: string): Promise<any> => {
  try {
    const apiUrl = getApiUrl();
    const response = await axios.get(`${apiUrl}/process/status/${processId}/render/`, {
      headers: headerBuilder({
        'Content-Type': 'application/json'
      })
    });
    return response.data;
  } catch (error) {
    console.error(`Error checking status for process ${processId}:`, error);
    throw error;
  }
};

// Helper function to create process and return process ID
export const createMigrationProcess = async (): Promise<string> => {
  try {
    const apiUrl = getApiUrl();
    const response = await axios.post(`${apiUrl}/process/create`, {}, {
      headers: headerBuilder({
        'Content-Type': 'application/json'
      })
    });
    return response.data.id;
  } catch (error) {
    console.error("Error creating migration process:", error);
    throw error;
  }
};

// Legacy function - commented out but kept for reference
/*
export const uploadFilesLegacy = async (files: File[]): Promise<any[]> => {
  const responses: any[] = [];

  for (let file of files) {
    const formData = new FormData();
    console.log(file)
    formData.append('file', file); // Use 'file' instead of 'files' for single file upload
    console.log(`Uploading file ${file.name}...`);
    console.log(formData)
    try {
      const apiUrl = getApiUrl();
      const response = await axios.post(`${apiUrl}/upload`, file, {
        headers: headerBuilder({
          'Content-Type': 'multipart/form-data',
        })
      });
      responses.push(response.data);
    } catch (error) {
      console.error(`Error uploading file ${file.name}:`, error);
      responses.push({ file: file.name, error: error.message });
    }
  }

  return responses;
};
*/
