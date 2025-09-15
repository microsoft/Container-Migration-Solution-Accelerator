import { StrictMode, useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import { FluentProvider, webLightTheme } from '@fluentui/react-components';
import { Provider } from 'react-redux';
import { store } from './store/store';
import AuthProvider from './msal-auth/AuthProvider';
import { setEnvData, setApiUrl, config as defaultConfig } from './api/config';
import { initializeMsalInstance } from './msal-auth/msalInstance';
import { debugScopes, debugTokenClaims } from './components/ScopeDebugger';
import { debugUserInfo } from './msal-auth/apiHeaders';

const Main = () => {
  const [isConfigLoaded, setIsConfigLoaded] = useState(false);
  const [msalInstance, setMsalInstance] = useState(null);
  const toBoolean = (value) => {
    if (typeof value !== 'string') {
      return false;
    }
    return value.trim().toLowerCase() === 'true';
  };
  const [config, setConfig] = useState(null);
  useEffect(() => {
    const initMsal = async () => {
      try {
        const response = await fetch('/config');
        let config = defaultConfig;
        
        if (response.ok) {
          config = await response.json();
          config.ENABLE_AUTH = toBoolean(config.ENABLE_AUTH);
          console.log('=====> Using backend config');
        } else {
          // Backend not available, use fallback configuration for testing
          console.log('====> Backend not available, using fallback config for testing');
          config = {
            ...defaultConfig,
            // Fallback MSAL configuration for testing
            ENABLE_AUTH: true, // Enable auth for testing
            REACT_APP_WEB_CLIENT_ID: import.meta.env.VITE_APP_WEB_CLIENT_ID || 'your-client-id-here',
            REACT_APP_WEB_AUTHORITY: import.meta.env.VITE_APP_WEB_AUTHORITY || 'https://login.microsoftonline.com/common',
            REACT_APP_REDIRECT_URL: import.meta.env.VITE_APP_REDIRECT_URL || window.location.origin,
            REACT_APP_POST_REDIRECT_URL: import.meta.env.VITE_APP_POST_REDIRECT_URL || window.location.origin,
            REACT_APP_WEB_SCOPE: import.meta.env.VITE_APP_WEB_SCOPE || 'User.Read',
            REACT_APP_API_SCOPE: import.meta.env.VITE_APP_API_SCOPE || 'User.Read',
            API_URL: 'http://localhost:8000/api' // Fallback API URL
          };
        }

        window.appConfig = config;
        setEnvData(config);
        setApiUrl(config.API_URL);
        setConfig(config);
        // Wait for MSAL to initialize before setting state
        const instance = config.ENABLE_AUTH ? await initializeMsalInstance(config) : {};
        setMsalInstance(instance);
        setIsConfigLoaded(true);

        // Make debug functions available globally for testing
        if (config.ENABLE_AUTH) {
          window.debugScopes = debugScopes;
          window.debugTokenClaims = debugTokenClaims;
          window.debugUserInfo = debugUserInfo;
          console.log('========> Debug functions available:');
          console.log('  - window.debugScopes() - Check scope configuration');
          console.log('  - window.debugTokenClaims() - Inspect token');
          console.log('  - window.debugUserInfo() - Check user info and headers');
        }
      } catch (error) {
        console.error("Error fetching config:", error);
        // If fetch fails completely, use fallback config
        console.log('========> Using fallback config due to fetch error');
        const config = {
          ...defaultConfig,
          ENABLE_AUTH: true, // Enable auth for testing
          REACT_APP_WEB_CLIENT_ID: import.meta.env.VITE_APP_WEB_CLIENT_ID || 'your-client-id-here',
          REACT_APP_WEB_AUTHORITY: import.meta.env.VITE_APP_WEB_AUTHORITY || 'https://login.microsoftonline.com/common',
          REACT_APP_REDIRECT_URL: import.meta.env.VITE_APP_REDIRECT_URL || window.location.origin,
          REACT_APP_POST_REDIRECT_URL: import.meta.env.VITE_APP_POST_REDIRECT_URL || window.location.origin,
          REACT_APP_WEB_SCOPE: import.meta.env.VITE_APP_WEB_SCOPE || 'User.Read',
          REACT_APP_API_SCOPE: import.meta.env.VITE_APP_API_SCOPE || 'User.Read',
          API_URL: 'http://localhost:8000/api'
        };
        
        window.appConfig = config;
        setEnvData(config);
        setApiUrl(config.API_URL);
        setConfig(config);
        const instance = config.ENABLE_AUTH ? await initializeMsalInstance(config) : {};
        setMsalInstance(instance);
        setIsConfigLoaded(true);

        // Make debug functions available globally for testing
        if (config.ENABLE_AUTH) {
          window.debugScopes = debugScopes;
          window.debugTokenClaims = debugTokenClaims;
          window.debugUserInfo = debugUserInfo;
          console.log('========> Debug functions available:');
          console.log('  - window.debugScopes() - Check scope configuration');
          console.log('  - window.debugTokenClaims() - Inspect token');
          console.log('  - window.debugUserInfo() - Check user info and headers');
        }
      }
    };

    initMsal(); // Call the async function inside useEffect
  }, []);
  async function checkConnection() {
    if (!config) return;

    const baseURL = config.API_URL.replace(/\/api$/, ''); // Remove '/api' if it appears at the end
    console.log('Checking connection to:', baseURL);
    try {
      const response = await fetch(`${baseURL}/health`);
      if (response.ok) {
        console.log('========> Backend connection successful');
      } else {
        console.log('========> Backend responded with error status:', response.status);
      }
    } catch (error) {
      console.log('========> Backend not available (this is okay for frontend-only testing):', error.message);
    }
  }

  // useEffect(() => {
  //   if (config) {
  //     checkConnection();
  //   }
  // }, [config]);

  if (!isConfigLoaded || !msalInstance) return <div>Loading...</div>;

  return (
    <StrictMode>
      <Provider store={store}>
        <FluentProvider theme={webLightTheme}>
          {config && config.ENABLE_AUTH ? (

            <AuthProvider msalInstance={msalInstance}>
              <App />
            </AuthProvider>
          ) : (

            <App />
          )}
        </FluentProvider>
      </Provider>
    </StrictMode>
  );
};

createRoot(document.getElementById('root')).render(<Main />);