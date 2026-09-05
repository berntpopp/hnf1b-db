import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';

import ReviewHeader from '@/components/review/ReviewHeader.vue';

const context = {
  phenopacket_id: 'PP-317',
  subject_label: 'HNF1B renal cysts',
  effective_state: 'in_review',
  has_published_head: true,
  candidate: {
    id: 42,
    revision_number: 7,
    content_sha256: `sha256:${'a'.repeat(64)}`,
  },
  audit: {
    owner: { username: 'curator.owner', display_name: 'Owner Curator' },
    submission: {
      id: 42,
      revision_number: 7,
      created_at: '2026-08-14T08:30:00Z',
      actor: { username: 'curator.submitter', display_name: 'Submitter Curator' },
      actor_role: 'curator',
      actor_role_at_decision_recorded: true,
    },
    contributors: [{ username: 'curator.contributor', display_name: 'Contributor Curator' }],
    approval: {
      id: 43,
      revision_number: 8,
      created_at: '2026-08-14T10:30:00Z',
      actor: { username: 'curator.reviewer', display_name: 'Reviewer Curator' },
      actor_role: 'curator',
      actor_role_at_decision_recorded: true,
    },
    publication: null,
  },
  capabilities: [
    { action: 'request_changes', allowed: true, blocked_by: [] },
    { action: 'approve', allowed: true, blocked_by: [] },
  ],
};

const stubs = {
  StateBadge: { props: ['state'], template: '<span class="state-badge">{{ state }}</span>' },
  'v-btn': {
    name: 'VBtn',
    props: ['to'],
    template:
      '<a :href="typeof to === `string` ? to : `/review`"><slot name="prepend" /><slot /></a>',
  },
  'v-icon': { template: '<i aria-hidden="true"><slot /></i>' },
};

function mountHeader(overrides = {}) {
  return mount(ReviewHeader, {
    props: { context, returnTo: '/review?tab=needs-review&page=3&q=renal', ...overrides },
    global: { stubs },
  });
}

describe('ReviewHeader', () => {
  it('renders one h1 plus candidate, ownership, submission, contributor, and approval audit data', () => {
    const wrapper = mountHeader();

    expect(wrapper.findAll('h1')).toHaveLength(1);
    expect(wrapper.get('h1').text()).toContain('PP-317');
    expect(wrapper.text()).toContain('HNF1B renal cysts');
    expect(wrapper.text()).toContain('Owner Curator');
    expect(wrapper.text()).toContain('Submitter Curator');
    expect(wrapper.text()).toContain('Contributor Curator');
    expect(wrapper.text()).toContain('Candidate revision 7');
    expect(wrapper.text()).toContain('Reviewer Curator');
    expect(wrapper.text()).toContain('role at decision: curator');
    expect(wrapper.text()).not.toContain('Role at decision not recorded');
    expect(wrapper.text()).toContain('Existing public version retained');
    expect(wrapper.text()).toContain('Eligible to review');
  });

  it('labels only a genuinely unrecorded historical role as missing', () => {
    const historical = structuredClone(context);
    historical.audit.approval.actor.role = 'admin';
    historical.audit.approval.actor_role = null;
    historical.audit.approval.actor_role_at_decision_recorded = false;
    const wrapper = mountHeader({ context: historical });

    expect(wrapper.text()).toContain('Role at decision not recorded');
    expect(wrapper.text()).not.toContain('role at decision: admin');
  });

  it('preserves the exact safe internal queue return path', () => {
    const wrapper = mountHeader();
    const back = wrapper.getComponent({ name: 'VBtn' });

    expect(back.props('to')).toBe('/review?tab=needs-review&page=3&q=renal');
    expect(back.text()).toContain('Back to review queue');
  });

  it.each([
    'https://attacker.example/review',
    '//attacker.example/review',
    '/review/PP-OTHER',
    '/phenopackets',
    '/review\\attacker.example',
  ])('rejects unsafe return path %s and falls back to the queue route', (returnTo) => {
    const wrapper = mountHeader({ returnTo });

    expect(wrapper.getComponent({ name: 'VBtn' }).props('to')).toEqual({ name: 'ReviewQueue' });
  });
});
