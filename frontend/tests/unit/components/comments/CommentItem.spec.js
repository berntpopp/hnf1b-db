/**
 * Unit tests for CommentItem.vue
 *
 * CommentItem renders a comment card with author info, body, optional
 * "Resolved" chip, and a conditional action menu (edit / resolve / delete).
 * Visibility of the action menu is controlled by the `canAct` computed:
 * true when the viewer is the comment's author OR has role "admin".
 *
 * These tests verify:
 *   1. "Resolved" chip is shown when comment.resolved_at is set.
 *   2. The action menu button is absent for a non-author, non-admin viewer.
 *
 * CommentEditHistory is also rendered by CommentItem (when comment.edited
 * is true). Our base fixture has edited=false, but we still mock the API
 * dependency to prevent accidental real network calls.
 */

import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

// Mock the comments API used by CommentEditHistory (child of CommentItem).
vi.mock('@/api/domain/comments', () => ({
  listCommentEdits: vi.fn().mockResolvedValue({ data: { data: [] } }),
  searchMentionableUsers: vi.fn().mockResolvedValue({ data: { data: [] } }),
}));

import CommentItem from '@/components/comments/CommentItem.vue';

const BASE_COMMENT = {
  id: 1,
  record_type: 'phenopacket',
  record_id: 'abc',
  author_id: 42,
  author_username: 'alice',
  author_display_name: 'Alice Example',
  body_markdown: 'hello',
  mentions: [],
  edited: false,
  resolved_at: null,
  resolved_by_id: null,
  created_at: '2026-04-14T10:00:00Z',
  updated_at: '2026-04-14T10:00:00Z',
  deleted_at: null,
  deleted_by_id: null,
};

function mountItem(commentOverrides = {}, viewerOverrides = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(CommentItem, {
    props: {
      comment: { ...BASE_COMMENT, ...commentOverrides },
      currentUserId: 99,
      currentUserRole: 'curator',
      ...viewerOverrides,
    },
    global: { plugins: [vuetify] },
  });
}

describe('CommentItem', () => {
  it('shows Resolved chip when comment.resolved_at is set', () => {
    const wrapper = mountItem({ resolved_at: '2026-04-14T11:00:00Z' });
    expect(wrapper.text()).toContain('Resolved');
  });

  it('does not show Resolved chip when comment is not resolved', () => {
    const wrapper = mountItem();
    expect(wrapper.text()).not.toContain('Resolved');
  });

  it('renders action menu button for the comment author', () => {
    // viewer is the author (id matches)
    const wrapper = mountItem({}, { currentUserId: 42 });
    expect(wrapper.find('[aria-label="Comment actions"]').exists()).toBe(true);
  });

  it('renders action menu button for an admin viewer', () => {
    const wrapper = mountItem({}, { currentUserId: 99, currentUserRole: 'admin' });
    expect(wrapper.find('[aria-label="Comment actions"]').exists()).toBe(true);
  });

  it('does not render action menu button for a non-author, non-admin viewer', () => {
    // userId 99 is not the author (42), role is curator (not admin) — canAct = false
    const wrapper = mountItem({}, { currentUserId: 99, currentUserRole: 'curator' });
    expect(wrapper.find('[aria-label="Comment actions"]').exists()).toBe(false);
  });
});
