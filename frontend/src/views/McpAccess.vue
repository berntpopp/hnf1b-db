<!-- src/views/McpAccess.vue -->
<!--
  MCP Access page.

  Explains how to connect the public, read-only HNF1B-db MCP server
  (https://mcp.hnf1b.org/mcp) to AI clients: Claude (web + desktop), ChatGPT,
  and coding agents (Claude Code, Codex CLI).

  This is an information page — the address it documents is an MCP transport
  endpoint for AI clients, not a website that renders in a browser.
-->
<template>
  <v-container class="py-8">
    <v-row justify="center">
      <v-col cols="12" md="10" lg="9">
        <!-- Header -->
        <div class="text-center mb-8">
          <v-avatar color="teal" size="80" class="mb-4">
            <v-icon size="48" color="white">mdi-robot-outline</v-icon>
          </v-avatar>
          <h1 class="text-h3 font-weight-bold text-grey-darken-3 mb-2">
            Connect an AI Agent (MCP)
          </h1>
          <p class="text-h6 text-grey-darken-1">
            Query HNF1B-db from Claude, ChatGPT, and coding agents over the Model Context Protocol
          </p>
        </div>

        <!-- Page-vs-endpoint notice -->
        <v-alert type="info" variant="tonal" class="mb-6" icon="mdi-information-outline">
          This page explains how to connect. The address below is an MCP
          <strong>transport endpoint for AI clients</strong> — not a website, so opening it in a
          browser will not show a page.
        </v-alert>

        <!-- What you get -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-teal-lighten-5">
            <v-icon left color="teal">mdi-database-search-outline</v-icon>
            What you get
          </v-card-title>
          <v-card-text class="pa-6">
            <p class="text-body-1 mb-3">
              A <strong>read-only</strong> connection to curated HNF1B gene, variant, individual,
              and publication data. Your agent can search the cohort, fetch phenopackets and
              variants, pull gene context and statistics, and cite publications — all without any
              write access.
            </p>
            <p class="text-body-2 text-grey-darken-1 mb-0">
              Public — no sign-in or API key required. Research use only; not clinical decision
              support.
            </p>
          </v-card-text>
        </v-card>

        <!-- Server address -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-teal-lighten-5">
            <v-icon left color="teal">mdi-link-variant</v-icon>
            Server address
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="d-flex align-center flex-wrap">
              <code class="endpoint-code mr-3">{{ endpoint }}</code>
              <v-btn
                size="small"
                variant="tonal"
                color="teal"
                prepend-icon="mdi-content-copy"
                @click="copy(endpoint, 'Server address')"
              >
                Copy
              </v-btn>
            </div>
            <p class="text-body-2 text-grey-darken-1 mt-3 mb-0">
              Transport: MCP Streamable HTTP. Use this same address in every client below.
            </p>
          </v-card-text>
        </v-card>

        <!-- Per-client instructions -->
        <h2 class="text-h5 font-weight-bold text-grey-darken-3 mb-4">How to connect</h2>
        <v-row>
          <v-col v-for="client in clients" :key="client.id" cols="12" md="6">
            <v-card class="h-100 d-flex flex-column" elevation="2">
              <v-card-title class="d-flex align-center">
                <v-icon :color="client.color" class="mr-2">{{ client.icon }}</v-icon>
                {{ client.name }}
              </v-card-title>
              <v-card-text class="flex-grow-1">
                <ol class="client-steps mb-3">
                  <li v-for="(step, i) in client.steps" :key="i" class="mb-1">{{ step }}</li>
                </ol>
                <div class="snippet-wrap">
                  <pre class="snippet"><code>{{ client.snippet }}</code></pre>
                  <v-btn
                    class="snippet-copy"
                    size="x-small"
                    variant="text"
                    icon="mdi-content-copy"
                    :aria-label="`Copy ${client.name} configuration`"
                    @click="copy(client.snippet, `${client.name} configuration`)"
                  />
                </div>
                <p v-if="client.note" class="text-caption text-grey-darken-1 mt-2 mb-0">
                  {{ client.note }}
                </p>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Verify tip -->
        <v-alert type="success" variant="tonal" class="mt-6" icon="mdi-check-circle-outline">
          Once connected, ask your agent to call <code>hnf1b_get_capabilities</code> first — it
          lists every available tool and how to use it.
        </v-alert>

        <p class="text-caption text-grey mt-4 mb-0">
          New to MCP? See the
          <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener noreferrer">
            Model Context Protocol
          </a>
          documentation.
        </p>
      </v-col>
    </v-row>

    <!-- Copy confirmation -->
    <v-snackbar v-model="snackbar" :timeout="2000" color="success">
      {{ snackbarMessage }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref } from 'vue';

// Public, read-only MCP transport endpoint (Streamable HTTP).
const endpoint = 'https://mcp.hnf1b.org/mcp';

// Connection recipes per client, verified against current (2026) official docs.
// Steps are intentionally short; the copy-pasteable command/config lives in
// `snippet`, and `note` carries the most important caveat.
const clients = [
  {
    id: 'claude',
    name: 'Claude (web & desktop)',
    icon: 'mdi-creation',
    color: 'deep-orange',
    steps: [
      'In Claude, open Customize → Connectors (claude.ai/customize/connectors).',
      'Click “+”, then “Add custom connector”.',
      'Paste the server address into the URL field and click Add (leave the OAuth fields empty).',
      'In a chat, open “+” → Connectors and toggle hnf1b-db on.',
    ],
    snippet: 'https://mcp.hnf1b.org/mcp',
    note: 'Same steps on claude.ai and Claude Desktop. Custom connectors are in beta; the Free plan allows one.',
  },
  {
    id: 'chatgpt',
    name: 'ChatGPT',
    icon: 'mdi-chat-processing-outline',
    color: 'green-darken-1',
    steps: [
      'On chatgpt.com, open Settings → Apps → Advanced settings and turn on Developer mode.',
      'Click “Create app”.',
      'Set Name to HNF1B-db, URL to the server address, Authentication to “No authentication”, then Create.',
      'In a chat, open “+” and enable the HNF1B-db app.',
    ],
    snippet: 'Name:  HNF1B-db\nURL:   https://mcp.hnf1b.org/mcp\nAuth:  No authentication',
    note: 'Web only (chatgpt.com); Plus, Pro, Business, Enterprise, or Edu. Developer mode is in beta.',
  },
  {
    id: 'claude-code',
    name: 'Claude Code',
    icon: 'mdi-console',
    color: 'blue-grey-darken-1',
    steps: [
      'Run the command below (flags go before the server name).',
      'For a shared/team setup, add --scope project to write it into .mcp.json.',
      'Verify with “claude mcp list”, or run “/mcp” inside a session.',
    ],
    snippet: 'claude mcp add --transport http hnf1b-db https://mcp.hnf1b.org/mcp',
    note: 'Or hand-edit .mcp.json → { "mcpServers": { "hnf1b-db": { "type": "http", "url": "…/mcp" } } }',
  },
  {
    id: 'codex',
    name: 'Codex CLI',
    icon: 'mdi-code-braces',
    color: 'indigo-darken-1',
    steps: [
      'Run the command below, or add the table to ~/.codex/config.toml by hand.',
      'Verify with “codex mcp list”, then start Codex.',
      'If it does not connect, update Codex to the latest release first.',
    ],
    snippet:
      'codex mcp add hnf1b-db --url https://mcp.hnf1b.org/mcp\n\n# or in ~/.codex/config.toml:\n[mcp_servers.hnf1b-db]\nurl = "https://mcp.hnf1b.org/mcp"',
    note: 'Remote Streamable-HTTP servers are first-class in current Codex releases.',
  },
];

// Copy confirmation snackbar state.
const snackbar = ref(false);
const snackbarMessage = ref('');

/**
 * Copy text to the clipboard and show a confirmation snackbar.
 * Mirrors the established clipboard pattern used in PageVariant.vue.
 */
const copy = (text, label) => {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        snackbarMessage.value = `${label} copied to clipboard`;
        snackbar.value = true;
        window.logService.debug('MCP page clipboard copy', { label });
      })
      .catch((err) => {
        snackbarMessage.value = 'Failed to copy to clipboard';
        snackbar.value = true;
        window.logService.warn('MCP page clipboard copy failed', {
          label,
          error: err.message,
        });
      });
  }
};
</script>

<style scoped>
.endpoint-code {
  padding: 0.35rem 0.6rem;
  border: 1px solid #cfd8e3;
  border-radius: 6px;
  background: #f6f8fb;
  color: #102033;
  font-size: 0.95rem;
  word-break: break-all;
}

.client-steps {
  padding-left: 1.15rem;
  font-size: 0.92rem;
  line-height: 1.5;
}

.snippet-wrap {
  position: relative;
}

.snippet {
  overflow-x: auto;
  margin: 0;
  padding: 0.75rem 2.25rem 0.75rem 0.85rem;
  border: 1px solid #cfd8e3;
  border-radius: 6px;
  background: #f6f8fb;
  color: #102033;
  font-size: 0.82rem;
  line-height: 1.45;
  white-space: pre;
}

.snippet-copy {
  position: absolute;
  top: 0.3rem;
  right: 0.3rem;
}
</style>
