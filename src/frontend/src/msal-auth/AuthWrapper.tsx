
import React, { useEffect, useState } from "react";
import { InteractionStatus } from "@azure/msal-browser";
import useAuth from './useAuth';

const AuthWrapper = ({ children }: { children: React.ReactNode }) => {

  const { isAuthenticated, login, inProgress, accounts, user } = useAuth();
  const [hasTriedLogin, setHasTriedLogin] = useState(false);

  useEffect(() => {
    // Only attempt login if:
    // 1. Not authenticated AND no accounts exist (completely new user)
    // 2. Haven't tried login before
    // 3. No interaction in progress
    const shouldLogin = !isAuthenticated && 
                       accounts.length === 0 && 
                       !hasTriedLogin && 
                       inProgress === InteractionStatus.None;

    if (shouldLogin) {
      console.log('Starting automatic login...');
      setHasTriedLogin(true);
      login().catch(error => {
        console.error('Auto-login failed:', error);
        // Reset the flag if login fails so user can try again
        setHasTriedLogin(false);
      });
    }

    // If we have accounts but not authenticated, log this for debugging
    if (accounts.length > 0 && !isAuthenticated) {
      console.log('Accounts exist but not authenticated yet, waiting for token...');
    }

    // If we have a user, we're good to go
    if (user) {
      console.log('Authentication complete, user ready:', user.username);
    }
  }, [isAuthenticated, inProgress, hasTriedLogin, login, accounts.length, user]);

  // Show loading state while interaction is in progress
  if (inProgress === InteractionStatus.Login || inProgress === InteractionStatus.HandleRedirect) {
    return React.createElement('div', null, 'Signing in...');
  }

  // Show loading while we have accounts but no user yet (waiting for token)
  if (accounts.length > 0 && !user) {
    return React.createElement('div', null, 'Setting up your session...');
  }

  // Only show children when we have an authenticated user
  return React.createElement(React.Fragment, null, (isAuthenticated && user) && children);
};

export default AuthWrapper;

