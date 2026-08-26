/**
 * Open-PC typed API client.
 *
 * Thin ergonomic wrapper over the generated Open-PC SDK (./client/sdk.gen.ts),
 * generated from the committed OpenAPI contract (../openapi.json) by
 * `@hey-api/openapi-ts`. The FastAPI server is the single source of truth; CI
 * fails if the committed spec drifts from the live server.
 *
 * The wrapper configures the generated client with the dashboard's `/api`
 * proxy base URL and the build-time REST auth token, and unwraps the hey-api
 * result envelope so callers get the parsed body (or a thrown error) directly —
 * mirroring the ergonomics of the old hand-rolled `fetch()` helper but with
 * typed request bodies from the contract.
 *
 * Inspired by SmolVM's `ts/src/index.ts` hand-written wrapper over its
 * generated client.
 */
import { client } from './client/client.gen'
import {
  capabilitiesCapabilitiesGet,
  focusWindowWindowsFocusPost,
  getScreenInfoScreenGet,
  keyboardHotkeyKeyboardHotkeyPost,
  keyboardPressKeyboardPressPost,
  keyboardTypeKeyboardTypePost,
  launchAppAppsLaunchPost,
  listWindowsWindowsGet,
  mouseClickMouseClickPost,
  mouseDoubleClickMouseDoubleClickPost,
  openUrlAppsOpenUrlPost,
  runCommandAppsRunPost,
} from './client/sdk.gen'

// ---- shared types (mirror the agent server's response shapes) ----

export interface ScreenInfo {
  width: number
  height: number
  cursor_x: number
  cursor_y: number
}

export interface WindowInfo {
  id: string
  title: string
  x: number
  y: number
  width: number
  height: number
}

export interface CommandResult {
  success: boolean
  stdout?: string
  stderr?: string
  return_code?: number
  error?: string
}

export interface ActionResult {
  success: boolean
  error?: string
  [key: string]: unknown
}

export interface Capabilities {
  name: string
  version: string
  transports: string[]
  ws_commands: string[]
  rest_endpoints: string[]
  limits: Record<string, unknown>
}

// ---- client configuration (runs once on module load) ----

const AUTH_TOKEN = import.meta.env.VITE_OPENPC_TOKEN

client.setConfig({
  baseUrl: '/api',
  headers: AUTH_TOKEN ? { 'X-OpenPC-Token': AUTH_TOKEN } : undefined,
})

// ---- unwrap the hey-api result envelope: parsed body, or throw ----

interface Envelope {
  data?: unknown
  error?: unknown
  response?: Response
}

async function unwrap<T>(p: Promise<Envelope>): Promise<T> {
  const r = await p
  if (r.data === undefined) {
    throw new Error(`API error: ${r.response?.status ?? 'no response'}`)
  }
  return r.data as T
}

// ---- ergonomic typed surface used by the dashboard ----

export const openpc = {
  screen: () => unwrap<ScreenInfo>(getScreenInfoScreenGet()),
  windows: async (): Promise<WindowInfo[]> => {
    const r = await unwrap<{ windows?: WindowInfo[] }>(listWindowsWindowsGet())
    return r.windows ?? []
  },
  runCommand: (command: string, timeout = 30) =>
    unwrap<CommandResult>(runCommandAppsRunPost({ body: { command, timeout } })),
  mouseClick: (x: number, y: number, button: 'left' | 'right' | 'middle' = 'left', clicks = 1) =>
    unwrap<ActionResult>(
      mouseClickMouseClickPost({ body: { x, y, button, clicks } })
    ),
  mouseDoubleClick: (x?: number, y?: number) =>
    unwrap<ActionResult>(mouseDoubleClickMouseDoubleClickPost({ body: { x, y } })),
  keyboardHotkey: (keys: string[]) =>
    unwrap<ActionResult>(keyboardHotkeyKeyboardHotkeyPost({ body: { keys } })),
  keyboardType: (text: string) =>
    unwrap<ActionResult>(keyboardTypeKeyboardTypePost({ body: { text } })),
  keyboardPress: (key: string) =>
    unwrap<ActionResult>(keyboardPressKeyboardPressPost({ body: { key } })),
  launchApp: (application: string) =>
    unwrap<ActionResult>(launchAppAppsLaunchPost({ body: { application } })),
  openUrl: (url: string) =>
    unwrap<ActionResult>(openUrlAppsOpenUrlPost({ body: { url } })),
  focusWindow: (window_id: string) =>
    unwrap<ActionResult>(focusWindowWindowsFocusPost({ body: { window_id } })),
  capabilities: () => unwrap<Capabilities>(capabilitiesCapabilitiesGet()),
}