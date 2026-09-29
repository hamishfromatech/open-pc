/**
 * Open-PC TypeScript/JavaScript SDK
 *
 * @example
 * ```typescript
 * import { OpenPCClient, ScreenInfo, ScreenshotResult } from '@openpc/sdk';
 *
 * const client = new OpenPCClient('localhost', 8090);
 * const screenshot = await client.screenshot();
 * ```
 */

export { OpenPCClient } from './api/client';
export * from './api/client';
export { BatchExecutor } from './batch';
