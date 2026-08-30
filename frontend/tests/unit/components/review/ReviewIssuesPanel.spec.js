/**
 * @vitest-environment jsdom
 *
 * Resolution rationales use the shared DOMPurify sanitizer, which requires
 * the repository's browser-compatible jsdom environment for security assertions.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { createComment, resolveComment, unresolveComment } = vi.hoisted(() => ({
  createComment: vi.fn(),
  resolveComment: vi.fn(),
  unresolveComment: vi.fn(),
}));

vi.mock('@/api/domain/comments', () => ({ createComment, resolveComment, unresolveComment }));

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
    resolution_events: [
      {
        id: 10,
        action: 'resolved',
        disposition: 'accepted_with_rationale',
        rationale: 'Evidence accepted <script>alert(1)</script>',
        actor_username: 'reviewer',
        created_at: '2026-08-14T10:00:00Z',
      },
      {
        id: 11,
        action: 'reopened',
        disposition: null,
        rationale: 'Candidate changed again',
        actor_username: 'second-reviewer',
        created_at: '2026-08-14T11:00:00Z',
      },
    ],
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
    attachTo: document.body,
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
        VAlert: { template: '<div><slot /></div>' },
        VBtn: {
          inheritAttrs: false,
          template: '<button v-bind="$attrs"><slot /></button>',
        },
        ReviewIssueDialog: {
          props: ['modelValue', 'mode'],
          emits: ['update:modelValue', 'submit'],
          template:
            '<button v-if="modelValue" data-testid="submit-create-dialog" @click="$emit(\'submit\', { bodyMarkdown: \'New issue\' })">Submit</button>',
        },
        CommentBody: { props: ['bodyMarkdown'], template: '<div>{{ bodyMarkdown }}</div>' },
      },
    },
  });
}

describe('ReviewIssuesPanel', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.clearAllMocks();
    createComment.mockResolvedValue({ data: { id: 56 } });
  });

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

  it('renders the ordered resolution audit with disposition and semantic timestamps', () => {
    const wrapper = mountPanel();
    const events = wrapper.findAll('[data-testid="resolution-event"]');

    expect(events).toHaveLength(2);
    expect(events[0].text()).toContain('Resolved by reviewer');
    expect(events[0].text()).toContain('Accepted with rationale');
    expect(events[0].text()).toContain('Evidence accepted');
    expect(events[0].html()).not.toContain('<script>');
    expect(events[1].text()).toContain('Reopened by second-reviewer');
    expect(events[1].text()).not.toContain('Disposition');

    const timestamps = wrapper.findAll('time');
    expect(timestamps.map((time) => time.attributes('datetime'))).toEqual([
      '2026-08-14T10:00:00Z',
      '2026-08-14T11:00:00Z',
    ]);
    expect(timestamps.every((time) => time.text().length > 0)).toBe(true);
  });

  it('replaces mutation controls with focused explicit reload recovery after a conflict', async () => {
    const reload = vi.fn().mockResolvedValue(null);
    createComment.mockRejectedValueOnce(
      Object.assign(new Error('Conflict'), {
        response: {
          status: 409,
          data: { detail: { code: 'review_closed', message: 'The review is closed.' } },
        },
      })
    );
    const wrapper = mountPanel({
      reload,
      createIssueCapability: { action: 'create_issue', allowed: true, blocked_by: [] },
    });

    await wrapper.get('[data-testid="create-issue"]').trigger('click');
    await wrapper.get('[data-testid="submit-create-dialog"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="issue-conflict-recovery"]').text()).toContain(
      'The review is closed.'
    );
    expect(wrapper.find('[data-testid="create-issue"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Resolve issue');
    expect(document.activeElement).toBe(
      wrapper.get('[data-testid="reload-issue-conflict"]').element
    );

    await wrapper.get('[data-testid="reload-issue-conflict"]').trigger('click');
    await flushPromises();
    expect(reload).toHaveBeenCalledOnce();
    expect(wrapper.find('[data-testid="issue-conflict-recovery"]').exists()).toBe(false);
  });
});
