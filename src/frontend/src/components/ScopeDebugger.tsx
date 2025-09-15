// scopeDebugHelper.ts - Console-based debugging utility
import { getConfigData } from '../msal-auth/msalInstance';
import { getScopeInfo, validateScopes } from '../msal-auth/scopeUtils';

export const debugScopes = () => {
  console.log('\n === MSAL SCOPE DEBUG SESSION ===');
  
  const configData = getConfigData();
  
  if (!configData) {
    console.warn(' XXXXXXXXXX> Config data not available. Make sure MSAL is initialized.');
    return;
  }

  // Validate scopes
  const isValid = validateScopes(configData);
  
  // Get detailed scope info
  const scopeInfo = getScopeInfo(configData);
  
  // Additional debug info
  console.log('\n Environment Variables Check:');
  console.log('REACT_APP_WEB_SCOPE:', configData.REACT_APP_WEB_SCOPE || import.meta.env.VITE_APP_WEB_SCOPE || 'Not set');
  console.log('REACT_APP_API_SCOPE:', configData.REACT_APP_API_SCOPE || import.meta.env.VITE_APP_API_SCOPE || 'Not set');
  console.log('REACT_APP_WEB_CLIENT_ID:', configData.REACT_APP_WEB_CLIENT_ID ? 'Set' : 'Not set');
  console.log('REACT_APP_WEB_AUTHORITY:', configData.REACT_APP_WEB_AUTHORITY ? 'Set' : 'Not set');
  
  console.log('\n Quick Test Instructions:');
  console.log('1. Check if scopes are valid:', isValid ? 'Valid' : 'Invalid');
  console.log('2. Login and watch for "Logging in with scopes:" message');
  console.log('3. Check token acquisition with "Requesting token with scopes:" message');
  console.log('4. Use localStorage to inspect stored tokens: localStorage.getItem("token")');
  
  console.log('\n === END DEBUG SESSION ===\n');
  
  return { isValid, scopeInfo, configData };
};

// Helper to check token scopes after authentication
export const debugTokenClaims = () => {
  const token = localStorage.getItem('token');
  
  if (!token) {
    console.warn('========> No token found in localStorage. Please login first.');
    return;
  }
  
  try {
    // Decode JWT token (basic parsing, not validation)
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    
    const claims = JSON.parse(jsonPayload);
    
    console.log('\n === TOKEN CLAIMS DEBUG ===');
    console.log('Audience (aud):', claims.aud);
    console.log('Scopes (scp):', claims.scp);
    console.log('Roles (roles):', claims.roles);
    console.log('App ID (appid):', claims.appid);
    console.log('Expires (exp):', new Date(claims.exp * 1000));
    console.log(' === END TOKEN DEBUG ===\n');
    
    return claims;
  } catch (error) {
    console.error('XXXXXXXXXX> Error decoding token:', error);
  }
};
