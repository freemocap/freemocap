/**
 * URL Service
 *
 * Provides centralized URL generation for all API endpoints and WebSocket connections.
 * This ensures consistency across the application and simplifies changes to URL structure.
 */

import config from '@/config/appConfig';

class UrlService {
  /**
   * Builds the base URL for HTTP requests
   */
  private getBaseUrl(): string {
    const { protocol, host, port } = config.server;
    return `${protocol}://${host}:${port}${config.server.basePath}`;
  }

  /**
   * Builds the base WebSocket URL
   */
  private getBaseWsUrl(): string {
    const { wsProtocol, host, port } = config.server;
    return `${wsProtocol}://${host}:${port}${config.server.basePath}`;
  }

  /**
   * Generates a complete API URL from a path
   */
  getApiUrl(path: string): string {
    return `${this.getBaseUrl()}${path}`;
  }

  /**
   * Generates a WebSocket connection URL
   */
  getWebSocketUrl(path: string = '/websocket/connect'): string {
    return `${this.getBaseWsUrl()}${path}`;
  }

  // Camera API endpoints
  getSkellycamUrls() {
    return {
      detectCameras: this.getApiUrl('/skellycam/camera/detect'),
      createCameraGroup: this.getApiUrl('/skellycam/camera/group/create'),
      closeAllCameras: this.getApiUrl('/skellycam/camera/group/close/all'),
      updateCameraConfigs: this.getApiUrl('/skellycam/camera/update'),
      startRecording: this.getApiUrl('/skellycam/camera/group/all/record/start'),
      stopRecording: this.getApiUrl('/skellycam/camera/group/all/record/stop'),
      pauseCameras: this.getApiUrl('/skellycam/camera/group/all/pause'),
      unpauseCameras: this.getApiUrl('/skellycam/camera/group/all/unpause'),
    };
  }
}

// Export as a singleton
export const urlService = new UrlService();
