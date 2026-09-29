/**
 * Open-PC TypeScript/JavaScript SDK Client
 * Async HTTP client for Open-PC Agent Server REST API.
 */

export interface ScreenInfo {
  width: number;
  height: number;
  cursor_x: number;
  cursor_y: number;
}

export interface ScreenshotResult {
  success: boolean;
  image?: string; // base64 encoded
  error?: string;
}

export interface LocationResult {
  success: boolean;
  x?: number;
  y?: number;
  confidence?: number;
  error?: string;
}

export interface WindowInfo {
  id: string;
  title: string;
  class_name: string;
}

export interface CommandResult {
  success: boolean;
  output?: string;
  error?: string;
}

export interface BatchStep {
  type: string;
  parameters: Record<string, unknown>;
}

export interface BatchResult {
  success: boolean;
  results: Array<{ type: string; result: Record<string, unknown> }>;
  [key: string]: unknown;
}

export type MouseButton = 'left' | 'right' | 'middle';
export type ScrollDirection = 'up' | 'down';

/**
 * Async client for Open-PC Agent Server.
 *
 * Usage:
 * ```typescript
 * const client = new OpenPCClient('localhost', 8090);
 * await client.screenshot();
 * ```
 */
export class OpenPCClient {
  private baseUrl: string;
  private token: string | null;

  constructor(host: string = 'localhost', port: number = 8090, token: string | null = null) {
    this.baseUrl = `http://${host}:${port}`;
    this.token = token;
  }

  private async request(
    method: string,
    endpoint: string,
    body?: unknown
  ): Promise<unknown> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['X-OpenPC-Token'] = this.token;
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return response.json();
    } else if (contentType.includes('image/png')) {
      const blob = await response.blob();
      const arrayBuffer = await blob.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
      return { success: true, image: base64 };
    } else {
      return { success: true, data: await response.text() };
    }
  }

  // ============== Health & Capabilities ==============

  async health(): Promise<unknown> {
    return (await this.request('GET', '/health')) as Record<string, unknown>;
  }

  async capabilities(): Promise<unknown> {
    return (await this.request('GET', '/capabilities')) as Record<string, unknown>;
  }

  // ============== Screenshot ==============

  async screenshot(): Promise<ScreenshotResult> {
    try {
      const result = await this.request('GET', '/screenshot/base64');
      return {
        success: (result as Record<string, unknown>).success as boolean,
        image: (result as Record<string, unknown>).image as string,
      };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  }

  async screenshotRegion(x: number, y: number, width: number, height: number): Promise<ScreenshotResult> {
    const endpoint = `/screenshot/region?x=${x}&y=${y}&width=${width}&height=${height}`;
    try {
      const result = await this.request('GET', endpoint);
      return {
        success: (result as Record<string, unknown>).success as boolean,
        image: (result as Record<string, unknown>).image as string,
      };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  }

  // ============== Screen Info ==============

  async screenInfo(): Promise<ScreenInfo> {
    return await this.request('GET', '/screen') as unknown as ScreenInfo;
  }

  // ============== Mouse Control ==============

  async mouseMove(x: number, y: number, duration: number = 0.0): Promise<unknown> {
    return this.request('POST', '/mouse/move', { x, y, duration });
  }

  async click(
    x: number | null = null,
    y: number | null = null,
    button: MouseButton = 'left',
    clicks: number = 1,
    duration: number = 0.0
  ): Promise<unknown> {
    return this.request('POST', '/mouse/click', { x, y, button, clicks, duration });
  }

  async doubleClick(x: number | null = null, y: number | null = null): Promise<unknown> {
    return this.request('POST', '/mouse/double-click', { x, y });
  }

  async rightClick(x: number | null = null, y: number | null = null): Promise<unknown> {
    return this.request('POST', '/mouse/right-click', { x, y });
  }

  async scroll(
    clicks: number = 3,
    direction: ScrollDirection = 'down',
    x: number | null = null,
    y: number | null = null
  ): Promise<unknown> {
    return this.request('POST', '/mouse/scroll', { clicks, direction, x, y });
  }

  async drag(
    startX: number, startY: number,
    endX: number, endY: number,
    duration: number = 0.5
  ): Promise<unknown> {
    return this.request('POST', '/mouse/drag', { start_x: startX, start_y: startY, end_x: endX, end_y: endY, duration });
  }

  async locateImage(imagePath: string, confidence: number = 0.9): Promise<LocationResult> {
    try {
      const result = await this.request('POST', '/mouse/locate', { image_path: imagePath, confidence });
      return {
        success: (result as Record<string, unknown>).success as boolean,
        x: (result as Record<string, unknown>).x as number,
        y: (result as Record<string, unknown>).y as number,
        confidence: (result as Record<string, unknown>).confidence as number,
      };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  }

  async locateImageBase64(imageB64: string, confidence: number = 0.9): Promise<LocationResult> {
    try {
      const result = await this.request('POST', '/mouse/locate-base64', { image_b64: imageB64, confidence });
      return {
        success: (result as Record<string, unknown>).success as boolean,
        x: (result as Record<string, unknown>).x as number,
        y: (result as Record<string, unknown>).y as number,
        confidence: (result as Record<string, unknown>).confidence as number,
      };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  }

  // ============== Keyboard Control ==============

  async type(text: string, interval: number = 0.05): Promise<unknown> {
    return this.request('POST', '/keyboard/type', { text, interval });
  }

  async pressKey(key: string): Promise<unknown> {
    return this.request('POST', '/keyboard/press', { key });
  }

  async hotkey(keys: string[]): Promise<unknown> {
    return this.request('POST', '/keyboard/hotkey', { keys });
  }

  async keyDown(key: string): Promise<unknown> {
    return this.request('POST', '/keyboard/down', { key });
  }

  async keyUp(key: string): Promise<unknown> {
    return this.request('POST', '/keyboard/up', { key });
  }

  // ============== Window Management ==============

  async listWindows(): Promise<WindowInfo[]> {
    return await this.request('GET', '/windows') as unknown as WindowInfo[];
  }

  async focusWindow(windowId: string): Promise<unknown> {
    return this.request('POST', '/windows/focus', { window_id: windowId });
  }

  async closeWindow(windowId: string): Promise<unknown> {
    return this.request('POST', '/windows/close', { window_id: windowId });
  }

  async maximizeWindow(windowId: string): Promise<unknown> {
    return this.request('POST', '/windows/maximize', { window_id: windowId });
  }

  async minimizeWindow(windowId: string): Promise<unknown> {
    return this.request('POST', '/windows/minimize', { window_id: windowId });
  }

  // ============== Applications ==============

  async launch(application: string): Promise<unknown> {
    return this.request('POST', '/apps/launch', { application });
  }

  async openUrl(url: string, browser: string = 'google-chrome'): Promise<unknown> {
    return this.request('POST', '/apps/open-url', { url, browser });
  }

  async runCommand(command: string, timeout: number = 30): Promise<CommandResult> {
    try {
      const result = await this.request('POST', '/apps/run', { command, timeout });
      return {
        success: (result as Record<string, unknown>).success as boolean,
        output: (result as Record<string, unknown>).output as string,
        error: (result as Record<string, unknown>).error as string,
      };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  }

  // ============== OCR ==============

  async ocr(
    x: number | null = null,
    y: number | null = null,
    width: number | null = null,
    height: number | null = null
  ): Promise<unknown> {
    const params = new URLSearchParams();
    if (x !== null) params.append('x', x.toString());
    if (y !== null) params.append('y', y.toString());
    if (width !== null) params.append('width', width.toString());
    if (height !== null) params.append('height', height.toString());
    const endpoint = params.toString() ? `/ocr?${params.toString()}` : '/ocr';
    return this.request('GET', endpoint) as Promise<unknown>;
  }

  // ============== Utilities ==============

  async wait(seconds: number): Promise<unknown> {
    return this.request('POST', '/wait', { seconds });
  }

  // ============== Batch Operations ==============

  async batch(steps: BatchStep[]): Promise<BatchResult> {
    const result = await this.request('POST', '/batch', { steps }) as Record<string, unknown>;
    return {
      success: result.success as boolean,
      results: result.results as Array<{ type: string; result: Record<string, unknown> }>
    };
  }

  // ============== Convenience Methods ==============

  async fillForm(fields: Array<{ text: string; key: string }>): Promise<unknown> {
    const steps: BatchStep[] = [];
    for (const field of fields) {
      steps.push({
        type: 'type',
        parameters: { text: field.text, interval: 0.02 }
      });
      steps.push({
        type: 'press',
        parameters: { key: 'tab' }
      });
    }
    steps.push({ type: 'press', parameters: { key: 'enter' } });
    return this.batch(steps);
  }

  async typeAndPress(text: string, key: string, interval: number = 0.05): Promise<BatchResult> {
    const steps: BatchStep[] = [
      { type: 'type', parameters: { text, interval } },
      { type: 'press', parameters: { key } }
    ];
    return this.batch(steps);
  }

  async moveToAndClick(x: number, y: number, duration: number = 0.5): Promise<BatchResult> {
    const steps: BatchStep[] = [
      { type: 'move_mouse', parameters: { x, y, duration } },
      { type: 'click', parameters: { x, y } }
    ];
    return this.batch(steps);
  }
}

export default OpenPCClient;
