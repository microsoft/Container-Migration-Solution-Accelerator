import { PublicClientApplication } from "@azure/msal-browser";
import { createMsalConfig } from "./msaConfig";
import { getScopeInfo, validateScopes } from "./scopeUtils";

let msalInstance: PublicClientApplication | null = null;
let configData: any = null;

export const initializeMsalInstance = async (config: any) => {
  if (!msalInstance) {
    configData = config;
    
    // Validate and log scope information
    validateScopes(configData);
    getScopeInfo(configData);
    
    msalInstance = new PublicClientApplication(createMsalConfig(configData));
    await msalInstance.initialize();
  }
  return msalInstance;
};

export const getMsalInstance = () => msalInstance;

export const getConfigData = () => configData;
