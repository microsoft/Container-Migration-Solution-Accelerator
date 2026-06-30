// Simple logging utility with levels and toggleable debug mode
type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogConfig {
  enableDebug: boolean;
  enableApiLogs: boolean;
  enableRenderLogs: boolean;
}

// Configuration - can be modified based on environment
const logConfig: LogConfig = {
  enableDebug: import.meta.env.DEV || false,
  enableApiLogs: true,
  enableRenderLogs: true,
};

class Logger {
  private formatMessage(level: LogLevel, component: string, message: string, data?: any): string {
    const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
    const formattedMessage = `[${timestamp}] ${level.toUpperCase()} [${component}] ${message}`;
    return data ? `${formattedMessage}` : formattedMessage;
  }

  debug(component: string, message: string, data?: any): void {
    if (!logConfig.enableDebug) return;
    console.log(this.formatMessage('debug', component, message), data || '');
  }

  info(component: string, message: string, data?: any): void {
    console.log(this.formatMessage('info', component, message), data || '');
  }

  warn(component: string, message: string, data?: any): void {
    console.warn(this.formatMessage('warn', component, message), data || '');
  }

  error(component: string, message: string, error?: any): void {
    console.error(this.formatMessage('error', component, message), error || '');
  }

  // Specialized methods for common patterns
  api(operation: string, status: 'start' | 'success' | 'error', details?: any): void {
    if (!logConfig.enableApiLogs) return;
    
    const statusEmoji = status === 'success' ? '✅' : status === 'error' ? '❌' : '🔄';
    const message = `${statusEmoji} API ${operation} - ${status}`;
    
    if (status === 'error') {
      this.error('API', message, details);
    } else {
      this.info('API', message, details);
    }
  }

  render(component: string, action: string, details?: any): void {
    if (!logConfig.enableRenderLogs) return;
    this.debug('Render', `${component} - ${action}`, details);
  }

  // Navigation logging
  navigation(from: string, to: string, reason?: string): void {
    const message = `Navigation: ${from} → ${to}${reason ? ` (${reason})` : ''}`;
    this.info('Navigation', message);
  }
}

// Export singleton instance
export const logger = new Logger();

// Export config for runtime modification if needed
export const setLogConfig = (newConfig: Partial<LogConfig>): void => {
  Object.assign(logConfig, newConfig);
};
