import { useState, useEffect } from 'react';
import { InteractionStatus, AccountInfo, PublicClientApplication } from "@azure/msal-browser";
import { getMsalInstance, getConfigData } from "./msalInstance"; // Import MSAL instance dynamically
import { createConfiguredRequests } from "./scopeUtils";
import { useIsAuthenticated, useMsal } from "@azure/msal-react"; // Still needed for tracking auth state

declare global {
  interface Window {
    activeUser: any;
    activeAccount: any;
    activeUserId: any;
    debugScopes: () => any;
    debugTokenClaims: () => any;
    debugUserInfo: () => any;
  }
}

interface User {
  username: string;
  name: string | undefined;
  shortName?: string;
  isInTeams: boolean;
  userId: string;
}

const useAuth = () => {
  const msalInstance: PublicClientApplication | null = getMsalInstance(); // Ensure it's always checked
  const isAuthenticated = useIsAuthenticated();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [hasInitialized, setHasInitialized] = useState(false);

  const accounts = msalInstance ? msalInstance.getAllAccounts() : [];
  const { inProgress } = useMsal();
  const activeAccount: AccountInfo | undefined = accounts[0];

  useEffect(() => {
    if (!msalInstance) {
      console.error("MSAL Instance is not initialized yet.");
      return;
    }

    if (accounts.length > 0 && !hasInitialized) {
      const activeUser = {
        username: accounts[0].username,
        name: accounts[0]?.name,
        isInTeams: false,
        userId: accounts[0].localAccountId
      };

      // Fix: Set user when we have an activeUser (not when we don't)
      setUser(activeUser);
      msalInstance.setActiveAccount(accounts[0]);

      // Store active user globally for headers
      window.activeUser = activeUser;
      window.activeAccount = accounts[0];  
      window.activeUserId = activeUser.userId;

      console.log("======>User authenticated:", activeUser.username);
      console.log("======>User ID (for headers):", activeUser.userId);

      const activeAccount = msalInstance.getActiveAccount();
      if (activeAccount && !token) {
        console.log("Fetching token...");
        getToken();
      }
      
      setHasInitialized(true);
    } else if (accounts.length === 0) {
      // Clear user state when no accounts
      setUser(null);
      window.activeUser = null;
      window.activeAccount = null;
      window.activeUserId = null;
      setHasInitialized(false);
    }
  }, [accounts.length, msalInstance, hasInitialized, token]); // Use hasInitialized to prevent re-runs

  const login = async () => {
    if (!msalInstance) {
      console.error("MSAL Instance is not available for login.");
      return;
    }

    // Check if an interaction is already in progress
    if (inProgress !== InteractionStatus.None) {
      console.warn("Login skipped - interaction already in progress:", inProgress);
      return;
    }

    const configData = getConfigData();
    if (!configData) {
      console.error("XXXXXXXXX> Config data is not available for login.");
      return;
    }

    const { loginRequest } = createConfiguredRequests(configData);

    try {
      if (accounts.length === 0) {
        console.log("Login request object:", loginRequest);
        console.log("Logging in with scopes:", loginRequest.scopes);
        await msalInstance.loginRedirect(loginRequest);
      } else {
        console.log("User already has accounts, skipping login");
      }
    } catch (error) {
      console.error("Login failed:", error);
      
      // Check for common errors and provide helpful messages
      if (error.message.includes("AADSTS50011")) {
        console.error("XXXXX> Redirect URI mismatch. Make sure http://localhost:5173 is registered in Azure AD.");
      } else if (error.message.includes("AADSTS700016")) {
        console.error("XXXXX> Application not found. Check your client ID in the .env file.");
      } else if (error.message.includes("interaction_in_progress")) {
        console.warn("XXXXX> Login already in progress, please wait...");
      }
    }
  };

  const logout = async () => {
    if (!msalInstance) {
      console.error("MSAL Instance is not available for logout.");
      return;
    }

    try {
      if (activeAccount) {
        await msalInstance.logoutRedirect({
          account: activeAccount,
        });
        localStorage.removeItem('token');
      } else {
        console.warn("No active account found for logout.");
      }
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  const getToken = async () => {
    if (!msalInstance) {
      console.error("MSAL Instance is not available to fetch token.");
      return;
    }

    const configData = getConfigData();
    if (!configData) {
      console.error(" XXXXXXXXX>Config data is not available for token request.");
      return;
    }

    const { loginRequest, tokenRequest } = createConfiguredRequests(configData);

    try {
      const activeAccount = msalInstance.getActiveAccount();

      if (!activeAccount) {
        console.error("No active account set. Please log in.");
        return;
      }

      const accessTokenRequest = {
        scopes: [...tokenRequest.scopes],
        account: activeAccount,
      };

      console.log("Requesting token with scopes:", tokenRequest.scopes);
      const response = await msalInstance.acquireTokenSilent(accessTokenRequest);
      const token = response.accessToken;
      localStorage.setItem('token', token);
      setToken(token);
      console.log("Token acquired successfully");
      console.log("Token available for API calls");
    } catch (error) {
      console.error("Error fetching token:", error);
      if (error.message.includes("interaction_required")) {
        console.log("Interaction required, redirecting to login with scopes:", loginRequest.scopes);
        await msalInstance.loginRedirect(loginRequest);
      }
    }
  };

  // Helper function to get user info for API headers
  const getUserForHeaders = () => {
    if (user && token) {
      return {
        userId: user.userId,
        username: user.username,
        token: token,
        // Principal ID is typically the localAccountId
        principalId: user.userId,
        // Object ID from the account
        objectId: activeAccount?.localAccountId,
        // Tenant ID if needed
        tenantId: activeAccount?.tenantId
      };
    }
    return null;
  };

  return {
    isAuthenticated,
    login,
    logout,
    user,
    accounts,
    inProgress,
    token,
    getToken,
    getUserForHeaders
  };
};

export default useAuth;
