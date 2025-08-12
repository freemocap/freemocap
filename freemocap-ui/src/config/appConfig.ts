/**
 * Application Configuration for Electron
 *
 * This module centralizes all configuration settings for the application,
 * including environment-specific settings, API endpoints, and other constants.
 */

const config = {
  // Server configuration
  server: {
    host: 'localhost', // Default for local development
    port: 8007, // Default port
    protocol: 'http',
    wsProtocol: 'ws',
    basePath: '',
  },

   // Application settings
  // TODO - replace hardcoded values throughout the app with these settings
  settings: {
    defaultRecordingDirectory: '',
    maxReconnectAttempts: 30,
    reconnectBackoffFactor: 2,
    maxReconnectDelay: 30000, // 30 seconds
  }
};

export default config;
