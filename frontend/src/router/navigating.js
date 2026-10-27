import { shallowRef } from 'vue';

// True while a navigation is pending (guards + lazy route chunk download);
// AppBar shows a progress bar so a click on a slow link gets feedback.
export const navigating = shallowRef(false);
