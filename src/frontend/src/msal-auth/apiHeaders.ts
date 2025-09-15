// apiHeaders.ts - Utility for creating API headers with user info
import { getMsalInstance } from './msalInstance';

export interface ApiHeaders {
  'Authorization': string;
  'X-User-Id': string;
  'X-Principal-Id': string;
  'X-User-Name': string;
  'X-Tenant-Id'?: string;
  'Content-Type': string;
}

/**
 * Get headers for API calls including authentication and user info
 */
export const getApiHeaders = (): ApiHeaders | null => {
  const token = localStorage.getItem('token');
  const activeUser = window.activeUser;
  const activeAccount = window.activeAccount;

  if (!token || !activeUser || !activeAccount) {
    console.warn('⚠️ Missing authentication data for API headers');
    return null;
  }

  return {
    'Authorization': `Bearer ${token}`,
    'X-User-Id': activeUser.userId,
    'X-Principal-Id': activeUser.userId, // Principal ID is the user ID
    'X-User-Name': activeUser.username,
    'X-Tenant-Id': activeAccount.tenantId || '',
    'Content-Type': 'application/json'
  };
};

/**
 * Get just the user principal ID for headers
 */
export const getPrincipalId = (): string | null => {
  const activeUser = window.activeUser;
  return activeUser?.userId || null;
};

/**
 * Get user info for debugging
 */
export const debugUserInfo = () => {
  console.log('=== User Info for API Headers ===');
  console.log('Active User:', window.activeUser);
  console.log('Active Account:', window.activeAccount);
  console.log('Token exists:', !!localStorage.getItem('token'));
  console.log('Headers would be:', getApiHeaders());
  console.log('================================');
  
  return {
    user: window.activeUser,
    account: window.activeAccount,
    hasToken: !!localStorage.getItem('token'),
    headers: getApiHeaders()
  };
};

// Make debug function available globally
if (typeof window !== 'undefined') {
  window.debugUserInfo = debugUserInfo;
}
