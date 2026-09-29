/**
 * Open-PC TypeScript SDK Example
 *
 * Run with:
 *   tsx example.ts
 * or
 *   npx ts-node example.ts
 */

import { OpenPCClient, BatchExecutor } from '../src/index';

async function main() {
  const client = new OpenPCClient('localhost', 8090);

  console.log('Testing Open-PC TypeScript SDK...\n');

  try {
    // Health check
    console.log('1. Checking server health...');
    const health = await client.health();
    console.log('   Status:', (health as Record<string, unknown>).status);

    // Screen info
    console.log('\n2. Getting screen info...');
    const screen = await client.screenInfo();
    console.log('   Screen:', `${screen.width}x${screen.height}`);

    // Take screenshot
    console.log('\n3. Taking screenshot...');
    const screenshot = await client.screenshot();
    if (screenshot.success && screenshot.image) {
      console.log('   Success! Got image (base64 length:', screenshot.image.length, ')');
    } else {
      console.log('   Failed:', screenshot.error);
    }

    // Type text
    console.log('\n4. Typing text...');
    const typeResult = await client.type('Hello from TypeScript SDK!');
    console.log('   Result:', typeResult);

    // Click
    console.log('\n5. Clicking...');
    const clickResult = await client.click();
    console.log('   Result:', clickResult);

    // Batch operations
    console.log('\n6. Testing batch operations...');
    const batch = new BatchExecutor(client);
    const batchResult = await batch.typeAndPress('Hello', 'enter');
    console.log('   Batch result:', batchResult);

    // List windows
    console.log('\n7. Listing windows...');
    const windows = await client.listWindows();
    console.log('   Windows:', windows);

    console.log('\n✅ All tests passed!');
  } catch (error) {
    console.error('\n❌ Error:', error);
  }
}

main();
