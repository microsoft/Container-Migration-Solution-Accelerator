// scopeUtils.ts
import { createLoginRequest, createTokenRequest } from './msaConfig';

export interface ScopeInfo {
  loginScopes: string[];
  tokenScopes: string[];
  configData: any;
}

// Function to get and log scope information
export const getScopeInfo = (configData: any): ScopeInfo => {
  // Handle case where configData is null/undefined
  if (!configData || typeof configData !== 'object') {
    console.warn('=== MSAL Scope Configuration (FALLBACK) ===');
    console.warn('Config data is null, undefined, or not an object:', configData);
    console.warn('Using default fallback scopes');
    
    const fallbackScopeInfo: ScopeInfo = {
      loginScopes: ["user.read"], // Default fallback
      tokenScopes: [], // Empty fallback
      configData: configData || {}
    };
    
    console.warn('Fallback Login Scopes:', fallbackScopeInfo.loginScopes);
    console.warn('Fallback Token Scopes:', fallbackScopeInfo.tokenScopes);
    console.warn('===============================================');
    
    return fallbackScopeInfo;
  }

  const loginRequest = createLoginRequest(configData);
  const tokenRequest = createTokenRequest(configData);
  
  const scopeInfo: ScopeInfo = {
    loginScopes: loginRequest.scopes,
    tokenScopes: tokenRequest.scopes,
    configData
  };

  console.log('=== MSAL Scope Configuration ===');
  console.log('Login Scopes:', scopeInfo.loginScopes);
  console.log('Token Scopes:', scopeInfo.tokenScopes);
  console.log('Config Data Keys:', Object.keys(configData));
  console.log('Raw WEB_SCOPE:', configData.REACT_APP_WEB_SCOPE);
  console.log('Raw API_SCOPE:', configData.REACT_APP_API_SCOPE);
  console.log('================================');
  
  return scopeInfo;
};

// Function to validate scopes are properly configured
export const validateScopes = (configData: any): boolean => {
  // Handle case where configData is null/undefined
  if (!configData || typeof configData !== 'object') {
    console.warn('=== Scope Validation ===');
    console.warn('Config data is null, undefined, or not an object:', configData);
    console.warn('Using fallback values');
    console.warn('=======================');
    return false;
  }

  const loginScope = configData.REACT_APP_WEB_SCOPE || '';
  const tokenScope = configData.REACT_APP_API_SCOPE || '';
  
  // Validate that we have the basic required config for MSAL
  const hasBasicConfig = !!(
    configData.REACT_APP_MSAL_AUTH_CLIENTID &&
    configData.REACT_APP_MSAL_AUTH_AUTHORITY &&
    configData.REACT_APP_MSAL_REDIRECT_URL
  );
  
  // For now, we'll consider it valid if we have basic MSAL config
  // The scopes are optional and may be empty for basic functionality
  const isValid = hasBasicConfig;
  
  console.log('=== Scope Validation ===');
  console.log('Login Scope (REACT_APP_WEB_SCOPE):', loginScope);
  console.log('Token Scope (REACT_APP_API_SCOPE):', tokenScope);
  console.log('Has Basic MSAL Config:', hasBasicConfig);
  console.log('Client ID Present:', !!configData.REACT_APP_MSAL_AUTH_CLIENTID);
  console.log('Authority Present:', !!configData.REACT_APP_MSAL_AUTH_AUTHORITY);
  console.log('Redirect URL Present:', !!configData.REACT_APP_MSAL_REDIRECT_URL);
  console.log('Scopes Valid:', isValid);
  console.log('=======================');
  
  return isValid;
};

// Function to create properly configured requests with current config
export const createConfiguredRequests = (configData: any) => {
  // Handle case where configData is null/undefined
  if (!configData || typeof configData !== 'object') {
    console.warn('Creating MSAL requests with fallback config due to missing/invalid configData');
    
    // Return safe fallback requests
    return {
      loginRequest: { scopes: ["user.read"] },
      tokenRequest: { scopes: [] }
    };
  }

  try {
    return {
      loginRequest: createLoginRequest(configData),
      tokenRequest: createTokenRequest(configData)
    };
  } catch (error) {
    console.error('Error creating MSAL requests, using fallbacks:', error);
    return {
      loginRequest: { scopes: ["user.read"] },
      tokenRequest: { scopes: [] }
    };
  }
};
