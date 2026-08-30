import { nextTick, ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';

const actionState = {
  pendingAction: ref(null),
  submitting: ref(false),
  error: ref(null),
  conflict: ref(null),
  approve: vi.fn(),
  requestChanges: vi.fn(),
  reopenApproved: vi.fn(),
  publish: vi.fn(),
  withdraw: vi.fn(),
};

vi.mock('@/composables/useReviewActions', () => ({ useReviewActions: () => actionState }));

import ReviewActionPanel from '@/components/review/ReviewActionPanel.vue';

const baseContext = () => ({
  phenopacket_id: 'PP-1',
  effective_state: 'in_review',
  candidate: { id: 42, content_sha256: `sha256:${'a'.repeat(64)}` },
  approved: null,
  discussion_summary: { open_blocking_issues: 0 },
  capabilities: [
    { action: 'request_changes', allowed: true, blocked_by: [] },
    { action: 'approve', allowed: true, blocked_by: [] },
  ],
});

const DecisionDialogStub = {
  props: ['modelValue', 'action', 'unresolvedCount', 'snapshot'],
  emits: ['update:modelValue', 'submit', 'closed'],
  template: `
    <div v-if="modelValue" data-testid="decision-dialog" :data-action="action">
      <button data-testid="close-dialog" @click="$emit('update:modelValue', false); $emit('closed')">
        Close
      </button>
    </div>
  `,
};

const stubs = {
  ReviewDecisionDialog: DecisionDialogStub,
  'v-alert': { template: '<section role="alert"><slot /><slot name="append" /></section>' },
  'v-btn': {
    props: ['disabled', 'loading'],
    template: '<button :disabled="disabled"><slot name="prepend" /><slot /></button>',
  },
  'v-icon': { template: '<i aria-hidden="true"><slot /></i>' },
};

let wrapper;

function mountPanel(context = baseContext(), overrides = {}) {
  wrapper = mount(ReviewActionPanel, {
    props: {
      context,
      reload: vi.fn(),
      ...overrides,
    },
    attachTo: document.body,
    global: { stubs },
  });
  return wrapper;
}

afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
});

describe('ReviewActionPanel', () => {
  beforeEach(() => {
    for (const key of ['approve', 'requestChanges', 'reopenApproved', 'publish', 'withdraw']) {
      actionState[key].mockReset().mockResolvedValue({});
    }
    actionState.pendingAction.value = null;
    actionState.submitting.value = false;
    actionState.error.value = null;
    actionState.conflict.value = null;
  });

  it('disables approval when issue status is unknown and explains the fail-closed state', () => {
    const context = baseContext();
    context.discussion_summary.open_blocking_issues = null;
    const panel = mountPanel(context);

    expect(panel.get('[data-testid="action-approve"]').attributes('disabled')).toBeDefined();
    expect(panel.text()).toContain('Blocking issue status is unavailable');
  });

  it('uses the unresolved count and server blocker to disable approval', () => {
    const context = baseContext();
    context.discussion_summary.open_blocking_issues = 2;
    context.capabilities[1] = {
      action: 'approve',
      allowed: false,
      blocked_by: ['unresolved_review_issues'],
    };
    const panel = mountPanel(context);

    expect(panel.get('[data-testid="action-approve"]').attributes('disabled')).toBeDefined();
    expect(panel.text()).toContain('2 unresolved blocking issues remain');
  });

  it('explains server-reported self-review and contribution denials', () => {
    const context = baseContext();
    context.capabilities = [
      {
        action: 'request_changes',
        allowed: false,
        blocked_by: ['self_review_forbidden', 'reviewer_contributed'],
      },
      {
        action: 'approve',
        allowed: false,
        blocked_by: ['self_review_forbidden', 'reviewer_contributed'],
      },
    ];
    const panel = mountPanel(context);

    expect(panel.text()).toContain('You own this draft');
    expect(panel.text()).toContain('You contributed content in this review cycle');
  });

  it('offers publication only when the backend supplies its capability', () => {
    const withoutPublish = mountPanel({ ...baseContext(), effective_state: 'approved' });
    expect(withoutPublish.find('[data-testid="action-publish"]').exists()).toBe(false);
    withoutPublish.unmount();

    const context = { ...baseContext(), effective_state: 'approved' };
    context.approved = { id: 43, content_sha256: `sha256:${'b'.repeat(64)}` };
    context.capabilities = [{ action: 'publish', allowed: true, blocked_by: [] }];
    const withPublish = mountPanel(context);

    expect(withPublish.get('[data-testid="action-publish"]').text()).toContain('Publish');
  });

  it('restores focus to the action that opened the modal', async () => {
    const panel = mountPanel();
    const trigger = panel.get('[data-testid="action-approve"]');
    trigger.element.focus();

    await trigger.trigger('click');
    expect(panel.get('[data-testid="decision-dialog"]').attributes('data-action')).toBe('approve');
    await panel.get('[data-testid="close-dialog"]').trigger('click');
    await nextTick();

    expect(document.activeElement).toBe(trigger.element);
  });

  it('replaces all decisions with the reload-required conflict state', async () => {
    actionState.conflict.value = {
      code: 'review_revision_mismatch',
      message: 'The candidate changed.',
      reloadRequired: true,
    };
    const reload = vi.fn().mockResolvedValue({});
    const panel = mountPanel(baseContext(), { reload });

    expect(panel.text()).toContain('The candidate changed.');
    expect(panel.find('[data-testid="action-approve"]').exists()).toBe(false);
    await panel.get('[data-testid="reload-review"]').trigger('click');
    expect(reload).toHaveBeenCalledOnce();
  });
});
