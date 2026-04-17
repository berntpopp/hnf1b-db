/**
 * Unit tests for CommentComposer.vue
 *
 * CommentComposer embeds a Tiptap rich-text editor with a markdown
 * extension and @-mention support. The submit button is disabled until
 * the body contains at least one non-whitespace character.
 *
 * Tiptap performs DOM operations (ProseMirror) that are incompatible with
 * happy-dom/jsdom. We therefore mock the three Tiptap packages plus the
 * tiptap-markdown extension so that `useEditor` returns a predictable stub.
 *
 * The mock controls `content.value` indirectly: `useEditor.onUpdate` is
 * never called, so `content` stays at whatever the prop initialised it to.
 * We test the "empty body → disabled submit" path (editingComment=null,
 * initial content = '') and the "pre-filled edit → enabled submit" path
 * (editingComment with a non-empty body_markdown).
 */

import { describe, it, expect, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Tiptap / extension mocks — must be declared BEFORE the component import.
// ---------------------------------------------------------------------------

vi.mock('@tiptap/vue-3', () => ({
  useEditor: vi.fn((opts) => {
    // Return a minimal editor ref-like object. The ref wrapper is not needed
    // here because the component calls `editor.value.*` — we return the
    // inner object directly and the component destructures via `.value`.
    const stub = {
      state: {
        doc: {
          descendants: vi.fn(),
        },
      },
      storage: {
        markdown: {
          getMarkdown: vi.fn(() => opts.content ?? ''),
        },
      },
      commands: {
        setContent: vi.fn(),
      },
      destroy: vi.fn(),
    };
    // Simulate onUpdate being called once so content ref gets the initial value.
    if (opts.onUpdate) {
      opts.onUpdate({ editor: stub });
    }
    // Return a Vue ref-like object with .value pointing to stub.
    return { value: stub };
  }),
  EditorContent: { template: '<div class="editor-content-stub" />' },
}));

vi.mock('@tiptap/starter-kit', () => ({ default: {} }));

vi.mock('@tiptap/extension-mention', () => ({
  default: {
    configure: vi.fn((opts) => ({ _isMentionStub: true, ...opts })),
  },
}));

vi.mock('tiptap-markdown', () => ({ Markdown: {} }));

vi.mock('@tiptap/extension-link', () => ({ default: {} }));

vi.mock('@/api/domain/comments', () => ({
  searchMentionableUsers: vi.fn().mockResolvedValue({ data: { data: [] } }),
  listCommentEdits: vi.fn().mockResolvedValue({ data: { data: [] } }),
}));

// ---------------------------------------------------------------------------
// Component import (after mocks are set up)
// ---------------------------------------------------------------------------

import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

import CommentComposer from '@/components/comments/CommentComposer.vue';

function mountComposer(props = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(CommentComposer, {
    props: {
      editingComment: null,
      submitting: false,
      ...props,
    },
    global: { plugins: [vuetify] },
  });
}

describe('CommentComposer', () => {
  it('mounts without throwing', () => {
    const wrapper = mountComposer();
    expect(wrapper.exists()).toBe(true);
  });

  // Helper: find the submit button by its rendered label (Post | Save).
  // The formatting toolbar introduced in H5 adds four buttons before the
  // submit, so a bare `wrapper.find('button')` no longer resolves to it.
  function findSubmitButton(wrapper) {
    return wrapper.findAll('button').find((b) => /^(post|save)$/i.test(b.text().trim()));
  }

  it('submit button is disabled when body is empty', () => {
    // editingComment=null → initial content = '' → canSubmit = false
    const wrapper = mountComposer({ editingComment: null });
    const btn = findSubmitButton(wrapper);
    expect(btn).toBeDefined();
    expect(btn.attributes('disabled')).toBeDefined();
  });

  it('submit button is enabled when editing comment with non-empty body', () => {
    // editingComment with a non-empty body_markdown → content = 'existing text' → canSubmit = true
    const wrapper = mountComposer({
      editingComment: { id: 5, body_markdown: 'existing text' },
      submitting: false,
    });
    const btn = findSubmitButton(wrapper);
    expect(btn).toBeDefined();
    expect(btn.attributes('disabled')).toBeUndefined();
  });

  it('shows "Save" label when editing an existing comment', () => {
    const wrapper = mountComposer({
      editingComment: { id: 5, body_markdown: 'existing text' },
    });
    expect(wrapper.text()).toContain('Save');
  });

  it('shows "Post" label when composing a new comment', () => {
    const wrapper = mountComposer({ editingComment: null });
    expect(wrapper.text()).toContain('Post');
  });

  // H5 — accessible name + formatting toolbar
  it('wires aria-label and aria-describedby onto ProseMirror via editorProps', async () => {
    const { useEditor } = await import('@tiptap/vue-3');
    mountComposer();
    expect(useEditor).toHaveBeenCalled();
    const call = useEditor.mock.calls.at(-1)[0];
    expect(call.editorProps?.attributes).toEqual(
      expect.objectContaining({
        'aria-label': 'Comment body',
        'aria-describedby': 'composer-char-count',
      })
    );
  });

  it('renders a formatting toolbar with role=toolbar and its own accessible name', () => {
    const wrapper = mountComposer();
    const toolbar = wrapper.find('[data-testid="composer-toolbar"]');
    expect(toolbar.exists()).toBe(true);
    expect(toolbar.attributes('role')).toBe('toolbar');
    expect(toolbar.attributes('aria-label')).toMatch(/comment formatting/i);
  });

  it('exposes Bold, Italic, Insert link, and Mention buttons with aria-labels', () => {
    const wrapper = mountComposer();
    const toolbar = wrapper.get('[data-testid="composer-toolbar"]');
    const labels = toolbar.findAll('button').map((b) => b.attributes('aria-label'));
    expect(labels).toEqual(
      expect.arrayContaining(['Bold', 'Italic', 'Insert link', 'Mention user'])
    );
  });

  it('gives the character counter a stable id so aria-describedby resolves', () => {
    const wrapper = mountComposer();
    const counter = wrapper.find('#composer-char-count');
    expect(counter.exists()).toBe(true);
    expect(counter.text()).toMatch(/\d+\s*\/\s*10000/);
  });
});
