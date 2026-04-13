// frontend/src/utils/stateConfig.js
// Wave 7 / D.1 — shared state-machine configuration used by StateBadge, TransitionMenu, etc.

export const STATE_COLORS = {
  draft: 'grey',
  in_review: 'blue',
  changes_requested: 'orange',
  approved: 'purple',
  published: 'green',
  archived: 'brown',
};

export const STATE_LABELS = {
  draft: 'Draft',
  in_review: 'In review',
  changes_requested: 'Changes requested',
  approved: 'Approved',
  published: 'Published',
  archived: 'Archived',
};

export const TRANSITION_LABELS = {
  in_review: 'Submit for review',
  changes_requested: 'Request changes',
  approved: 'Approve',
  published: 'Publish',
  archived: 'Archive',
  draft: 'Withdraw',
};
