/**
 * Tests for McpAccess.vue — the "Connect an AI Agent (MCP)" page.
 *
 * Verifies the observable, user-facing behavior: the public endpoint is
 * documented, the page is clearly distinguished from the transport endpoint,
 * all four supported clients are listed with their copy-pasteable config, and
 * the copy-to-clipboard action works. Vuetify is registered globally in
 * tests/setup.js, so no per-test plugin wiring is needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

import McpAccess from '@/views/McpAccess.vue';

const ENDPOINT = 'https://mcp.hnf1b.org/mcp';

describe('McpAccess view', () => {
  let writeText;
  let vuetify;

  beforeEach(() => {
    vuetify = createVuetify({ components, directives });
    writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
      writable: true,
    });
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const factory = () => mount(McpAccess, { global: { plugins: [vuetify] } });

  it('documents the public MCP endpoint', () => {
    const wrapper = factory();
    expect(wrapper.text()).toContain(ENDPOINT);
  });

  it('clarifies that the address is a transport endpoint, not a browser page', () => {
    const wrapper = factory();
    expect(wrapper.text().toLowerCase()).toContain('not a website');
  });

  it('lists all four supported clients', () => {
    const text = factory().text();
    expect(text).toContain('Claude (web & desktop)');
    expect(text).toContain('ChatGPT');
    expect(text).toContain('Claude Code');
    expect(text).toContain('Codex CLI');
  });

  it('shows the Claude Code add command and the Codex config table', () => {
    const text = factory().text();
    expect(text).toContain(`claude mcp add --transport http hnf1b-db ${ENDPOINT}`);
    expect(text).toContain('[mcp_servers.hnf1b-db]');
  });

  it('copies the server address to the clipboard', async () => {
    const wrapper = factory();
    const copyBtn = wrapper.findAll('button').find((b) => b.text().includes('Copy'));
    expect(copyBtn).toBeTruthy();
    await copyBtn.trigger('click');
    await flushPromises();
    expect(writeText).toHaveBeenCalledWith(ENDPOINT);
  });
});
