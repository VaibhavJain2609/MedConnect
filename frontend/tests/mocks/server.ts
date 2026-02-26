/**
 * MSW Server
 * Sets up mock service worker for Node.js environment (testing)
 */

import { setupServer } from 'msw/node'
import { handlers } from './handlers'

// This configures a request mocking server with the given request handlers
export const server = setupServer(...handlers)
