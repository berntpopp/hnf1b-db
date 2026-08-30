import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';

import ReviewIssuesPanel from '@/components/review/ReviewIssuesPanel.vue';

const issues = [
  {
    id: 2,
    author_username: 'reviewer',
    body_markdown: 'Resolved issue',
    created_at: '2026-08-14T09:00:00Z',
    resolved_at: '2026-08-14T10:00:00Z',
    review_revision_id: 42,
    capabilities: [{ action: 'reopen', allowed: true, blocked_by: [] }],
    resolution_events: [],
  },
  {
    id: 1,
    author_username: 'other-reviewer',
    body_markdown: 'Open issue',
    created_at: '2026-08-14T11:00:00Z',
    resolved_at: null,
    review_revision_id: 42,
    capabilities: [{ action: 'resolve', allowed: true, blocked_by: [] }],
    resolution_events: [],
  },
];

function mountPanel(overrides = {}) {
  return mount(ReviewIssuesPanel, {
    props: {
      issues,
      recordId: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
      recordRevision: 11,
      candidateRevisionId: 42,
      createIssueCapability: {
        action: 'create_issue',
        allowed: false,
        blocked_by: ['reviewer_submitted'],
      },
      reload: async () => null,
      liveMessage: '1 open blocking issue remains.',
      ...overrides,
    },
    global: {
      stubs: {
        ReviewIssueDialog: true,
        CommentBody: { props: ['bodyMarkdown'], template: '<div>{{ bodyMarkdown }}</div>' },
      },
    },
  });
}

describe('ReviewIssuesPanel', () => {
  it('orders unresolved issues first and exposes a non-color status label', () => {
    const wrapper = mountPanel();
    const rows = wrapper.findAll('[data-testid="review-issue"]');

    expect(rows[0].text()).toContain('Open issue');
    expect(rows[0].text()).toContain('Open');
    expect(rows[1].text()).toContain('Resolved issue');
    expect(rows[1].text()).toContain('Resolved');
  });

  it('uses each issue server capability and never offers Delete', () => {
    const wrapper = mountPanel();

    expect(wrapper.text()).toContain('Resolve issue');
    expect(wrapper.text()).toContain('Reopen issue');
    expect(wrapper.text()).not.toContain('Delete');
    const create = wrapper.get('[data-testid="create-issue"]');
    expect(create.attributes('disabled')).toBeDefined();
    expect(wrapper.text()).toContain('reviewer submitted');
  });

  it('renders the context issue-count announcement as a live status', () => {
    const wrapper = mountPanel();

    expect(wrapper.get('[role="status"]').attributes('aria-live')).toBe('polite');
    expect(wrapper.get('[role="status"]').text()).toBe('1 open blocking issue remains.');
  });
});
