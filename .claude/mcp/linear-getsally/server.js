#!/usr/bin/env node
/**
 * Wrapper that patches linear-mcp to use apiKey instead of accessToken
 * for Personal Access Tokens (lin_api_*).
 */
import { LinearClient } from '@linear/sdk';

// Patch: intercept LinearClient creation to use apiKey for PATs
const OriginalLinearClient = LinearClient;
const token = process.env.LINEAR_ACCESS_TOKEN;

if (token && token.startsWith('lin_api_')) {
  // Monkey-patch the LinearAuth.initialize to use apiKey
  const authModule = await import('./node_modules/linear-mcp/build/auth.js');
  const origInit = authModule.LinearAuth.prototype.initialize;
  authModule.LinearAuth.prototype.initialize = function(config) {
    if (config.type === 'pat') {
      this.tokenData = {
        accessToken: config.accessToken,
        refreshToken: '',
        expiresAt: Number.MAX_SAFE_INTEGER,
      };
      this.linearClient = new OriginalLinearClient({
        apiKey: config.accessToken,
      });
      return;
    }
    return origInit.call(this, config);
  };
}

// Now import and run the original server
await import('./node_modules/linear-mcp/build/index.js');
