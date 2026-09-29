/**
 * Open-PC SDK Batch Executor
 *
 * Provides high-level helpers for atomic batch operations.
 */

import { OpenPCClient } from './api/client';
import { BatchStep, BatchResult } from './api/client';

export class BatchExecutor {
  private client: OpenPCClient;

  constructor(client: OpenPCClient) {
    this.client = client;
  }

  async execute(steps: BatchStep[]): Promise<BatchResult> {
    return this.client.batch(steps);
  }

  /**
   * Fill multiple form fields, tabbing between them.
   */
  async fillForm(
    fields: Array<{ text: string; key: string }>,
    submitKey: string = 'enter'
  ): Promise<BatchResult> {
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
    steps.push({ type: 'press', parameters: { key: submitKey } });
    return this.execute(steps);
  }

  /**
   * Type text then press a key.
   */
  async typeAndPress(
    text: string,
    key: string,
    interval: number = 0.05
  ): Promise<BatchResult> {
    return this.execute([
      { type: 'type', parameters: { text, interval } },
      { type: 'press', parameters: { key } }
    ]);
  }

  /**
   * Move to coordinates then click.
   */
  async moveToAndClick(
    x: number,
    y: number,
    duration: number = 0.5
  ): Promise<BatchResult> {
    return this.execute([
      { type: 'move_mouse', parameters: { x, y, duration } },
      { type: 'click', parameters: { x, y } }
    ]);
  }

  /**
   * Type text then click.
   */
  async typeAndClick(
    text: string,
    x: number,
    y: number,
    interval: number = 0.05,
    duration: number = 0.5
  ): Promise<BatchResult> {
    return this.execute([
      { type: 'type', parameters: { text, interval } },
      { type: 'click', parameters: { x, y, duration } }
    ]);
  }

  /**
   * Execute hotkey sequences with optional pauses between.
   */
  async hotkeySequence(
    sequences: string[][],
    waitBetween: number = 0.5
  ): Promise<BatchResult> {
    const steps: BatchStep[] = [];
    for (let i = 0; i < sequences.length; i++) {
      steps.push({ type: 'hotkey', parameters: { keys: sequences[i] } });
      if (waitBetween > 0 && i < sequences.length - 1) {
        steps.push({ type: 'wait', parameters: { seconds: waitBetween } });
      }
    }
    return this.execute(steps);
  }

  /**
   * Wait then click.
   */
  async waitAndClick(
    seconds: number,
    x: number,
    y: number
  ): Promise<BatchResult> {
    return this.execute([
      { type: 'wait', parameters: { seconds } },
      { type: 'click', parameters: { x, y } }
    ]);
  }
}
