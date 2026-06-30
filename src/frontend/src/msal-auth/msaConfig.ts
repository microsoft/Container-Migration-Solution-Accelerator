// msalConfig.ts
import { Configuration, LogLevel } from '@azure/msal-browser';

export const createMsalConfig = (configData: any): Configuration => {
  // Handle case where configData is null/undefined
  if (!configData || typeof configData !== 'object') {
    console.error('createMsalConfig: configData is null/undefined, using empty fallback config');
    console.error('This will likely cause MSAL authentication to fail');
    
    return {
      auth: {
        clientId: '',
        authority: '',
        redirectUri: '',
        postLogoutRedirectUri: '',
      },
      cache: {
        cacheLocation: 'localStorage',
        storeAuthStateInCookie: false,
      },
      system: {
        loggerOptions: {
          loggerCallback: (level, message, containsPii) => {
            if (containsPii) return;
            if (level === LogLevel.Error) console.error(message);
          },
        },
      },
    };
  }

  return {
    auth: {
      clientId: configData.REACT_APP_MSAL_AUTH_CLIENTID || '',
      authority: configData.REACT_APP_MSAL_AUTH_AUTHORITY || '',
      redirectUri: configData.REACT_APP_MSAL_REDIRECT_URL || '',
      postLogoutRedirectUri: configData.REACT_APP_MSAL_POST_REDIRECT_URL || '',
    },
    cache: {
      cacheLocation: 'localStorage', // Use localStorage for persistent cache
      storeAuthStateInCookie: false,
    },
    system: {
      loggerOptions: {
        loggerCallback: (level, message, containsPii) => {
          if (containsPii) return;
          if (level === LogLevel.Error) console.error(message);
          // if (level === LogLevel.Info) console.info(message);
          // if (level === LogLevel.Verbose) console.debug(message);
          // if (level === LogLevel.Warning) console.warn(message);
        },
      },
    },
  };
};

// Create scope helper functions that use configData
export const createLoginRequest = (configData: any) => {
  // Handle case where configData is null/undefined
  if (!configData || typeof configData !== 'object') {
    console.warn('createLoginRequest: configData is null/undefined, using fallback scopes');
    return {
      scopes: ["user.read"], // Safe fallback
    };
  }

  const loginScope = configData.REACT_APP_WEB_SCOPE;
  
  // Handle various falsy values and empty strings
  if (!loginScope || loginScope.trim() === '') {
    console.log('createLoginRequest: No WEB_SCOPE defined, using default user.read');
    return {
      scopes: ["user.read"], // Default scope
    };
  }
  
  // Only include the loginScope if it's not empty after trimming
  const trimmedScope = loginScope.trim();
  const scopes = ["user.read", trimmedScope];
  
  console.log('createLoginRequest: Using scopes:', scopes);
  return {
    scopes: scopes,
  };
};

export const createTokenRequest = (configData: any) => {
  // Handle case where configData is null/undefined
  if (!configData || typeof configData !== 'object') {
    console.warn('createTokenRequest: configData is null/undefined, using empty scopes');
    return {
      scopes: [], // Safe fallback
    };
  }

  const tokenScope = configData.REACT_APP_API_SCOPE;
  
  // Handle various falsy values and empty strings
  if (!tokenScope || tokenScope.trim() === '') {
    console.log('createTokenRequest: No API_SCOPE defined, using empty scopes');
    return {
      scopes: [], // Empty scopes when no API scope is defined
    };
  }
  
  // Only include the tokenScope if it's not empty after trimming
  const trimmedScope = tokenScope.trim();
  const scopes = [trimmedScope];
  
  console.log('createTokenRequest: Using scopes:', scopes);
  return {
    scopes: scopes,
  };
};

export const graphConfig = {
  graphMeEndpoint: "https://graph.microsoft.com/v1.0/me",
};

// For backward compatibility - these will need configData to be passed
export const loginRequest = {
  scopes: ["user.read"],  // Default scope, should be updated with createLoginRequest
};

export const tokenRequest = {
  scopes: [],  // Default empty, should be updated with createTokenRequest
};