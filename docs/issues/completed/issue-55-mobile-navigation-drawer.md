# Issue #55: feat(frontend): add mobile-responsive navigation drawer

## Overview

Add responsive mobile navigation to HNF1B-DB frontend with hamburger menu and slide-out drawer for mobile devices.

**Current:** Desktop-only AppBar (navigation inaccessible on mobile <960px)
**Target:** Responsive navigation (hamburger menu + drawer for mobile, inline buttons for desktop)

## Why This Matters

**Problem:**
- Navigation only works on desktop (≥960px)
- Mobile users (<960px) cannot access main navigation
- Poor mobile user experience
- No hamburger menu for small screens
- Violates responsive design best practices

**Solution:**
- Add hamburger menu icon for mobile devices
- Create slide-out navigation drawer (Vuetify v-navigation-drawer)
- Maintain existing desktop navigation (inline buttons)
- Single source of truth for navigation items (DRY principle)

## Implementation

### New Files

**1. `frontend/src/config/navigationItems.js` (~30 lines)**
- Single source of truth for navigation structure
- DRY principle - no duplication between AppBar and MobileDrawer
- Icon, label, route, authentication requirements

**Example:**
```javascript
export const navigationItems = [
  { icon: 'mdi-home', label: 'Home', route: '/', requiresAuth: false },
  { icon: 'mdi-account-multiple', label: 'Phenopackets', route: '/phenopackets', requiresAuth: true },
  { icon: 'mdi-dna', label: 'Variants', route: '/variants', requiresAuth: true },
  { icon: 'mdi-book-open-variant', label: 'Publications', route: '/publications', requiresAuth: true },
  { icon: 'mdi-chart-bar', label: 'Aggregations', route: '/aggregations', requiresAuth: true },
];
```

**2. `frontend/src/components/MobileDrawer.vue` (~90 lines)**
- Vuetify v-navigation-drawer component
- Mobile-only (hidden on desktop)
- Opens from left side
- Lists all navigation items with icons
- User menu at bottom
- Closes on navigation or overlay click

**Template:**
```vue
<template>
  <v-navigation-drawer
    v-model="drawer"
    temporary
    location="left"
    :width="280"
  >
    <!-- Header with logo -->
    <v-list-item class="px-2">
      <v-list-item-title class="text-h6">HNF1B Database</v-list-item-title>
    </v-list-item>

    <v-divider />

    <!-- Navigation Items -->
    <v-list density="compact" nav>
      <v-list-item
        v-for="item in visibleNavItems"
        :key="item.route"
        :to="item.route"
        @click="drawer = false"
      >
        <template #prepend>
          <v-icon>{{ item.icon }}</v-icon>
        </template>
        <v-list-item-title>{{ item.label }}</v-list-item-title>
      </v-list-item>
    </v-list>

    <v-divider />

    <!-- User Menu (if authenticated) -->
    <v-list v-if="isAuthenticated" density="compact">
      <v-list-item @click="logout">
        <template #prepend>
          <v-icon>mdi-logout</v-icon>
        </template>
        <v-list-item-title>Logout</v-list-item-title>
      </v-list-item>
    </v-list>

    <v-list v-else density="compact">
      <v-list-item to="/login">
        <template #prepend>
          <v-icon>mdi-login</v-icon>
        </template>
        <v-list-item-title>Login</v-list-item-title>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>

<script>
import { navigationItems } from '@/config/navigationItems';
import { isAuthenticated } from '@/utils/auth';

export default {
  name: 'MobileDrawer',
  data() {
    return {
      drawer: false,
      navigationItems
    };
  },
  computed: {
    isAuthenticated() {
      return isAuthenticated();
    },
    visibleNavItems() {
      return this.navigationItems.filter(item => {
        if (item.requiresAuth && !this.isAuthenticated) {
          return false;
        }
        return true;
      });
    }
  },
  methods: {
    toggle() {
      this.drawer = !this.drawer;
    },
    logout() {
      localStorage.removeItem('token');
      this.$router.push('/login');
      this.drawer = false;
    }
  }
};
</script>
```

### Modified Files

**1. `frontend/src/components/AppBar.vue`**

Add hamburger menu button (mobile only):

```vue
<template>
  <v-app-bar app>
    <!-- Hamburger Menu (Mobile Only) -->
    <v-app-bar-nav-icon
      @click="toggleDrawer"
      class="d-md-none"
    />

    <!-- Logo -->
    <v-toolbar-title>HNF1B Database</v-toolbar-title>

    <v-spacer />

    <!-- Navigation Buttons (Desktop Only) -->
    <div class="d-none d-md-flex">
      <v-btn
        v-for="item in visibleNavItems"
        :key="item.route"
        :to="item.route"
        variant="text"
      >
        <v-icon left>{{ item.icon }}</v-icon>
        {{ item.label }}
      </v-btn>
    </div>

    <!-- User Menu (Desktop & Mobile) -->
    <v-menu v-if="isAuthenticated">
      <template #activator="{ props }">
        <v-btn icon v-bind="props">
          <v-icon>mdi-account-circle</v-icon>
        </v-btn>
      </template>
      <v-list>
        <v-list-item @click="logout">
          <v-list-item-title>Logout</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-menu>

    <v-btn v-else to="/login" variant="text">
      Login
    </v-btn>
  </v-app-bar>
</template>

<script>
import { navigationItems } from '@/config/navigationItems';
import { isAuthenticated } from '@/utils/auth';

export default {
  name: 'AppBar',
  data() {
    return {
      navigationItems
    };
  },
  computed: {
    isAuthenticated() {
      return isAuthenticated();
    },
    visibleNavItems() {
      return this.navigationItems.filter(item => {
        if (item.requiresAuth && !this.isAuthenticated) {
          return false;
        }
        return true;
      });
    }
  },
  methods: {
    toggleDrawer() {
      this.$emit('toggle-drawer');
    },
    logout() {
      localStorage.removeItem('token');
      this.$router.push('/login');
    }
  }
};
</script>
```

**2. `frontend/src/App.vue`**

Add MobileDrawer component and wire up toggle:

```vue
<template>
  <v-app>
    <AppBar @toggle-drawer="$refs.mobileDrawer.toggle()" />
    <MobileDrawer ref="mobileDrawer" />

    <v-main>
      <router-view />
    </v-main>

    <FooterBar />
  </v-app>
</template>

<script>
import AppBar from '@/components/AppBar.vue';
import MobileDrawer from '@/components/MobileDrawer.vue';
import FooterBar from '@/components/FooterBar.vue';

export default {
  name: 'App',
  components: {
    AppBar,
    MobileDrawer,
    FooterBar
  }
};
</script>
```

**3. `frontend/src/utils/auth.js`**

Add helper to get current user info (optional):

```javascript
export function getCurrentUser() {
  const token = localStorage.getItem('token');
  if (!token) return null;

  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return {
      username: payload.sub,
      exp: payload.exp
    };
  } catch (error) {
    return null;
  }
}
```

### Dependency Update

**Update Vuetify to latest stable:**

```bash
cd frontend
npm install vuetify@^3.10.6
```

**Current:** Vuetify 3.8.12
**Target:** Vuetify 3.10.6 (latest stable)

**Why:** Bug fixes, better mobile support, performance improvements

## Breakpoints

Vuetify breakpoints used:

| Breakpoint | Width | Navigation Style |
|------------|-------|------------------|
| `xs` | 0-599px | Hamburger + Drawer |
| `sm` | 600-959px | Hamburger + Drawer |
| `md` | 960-1279px | Inline Buttons |
| `lg` | 1280-1919px | Inline Buttons |
| `xl` | 1920px+ | Inline Buttons |

**Implementation:**
- Mobile: `class="d-md-none"` (display only <960px)
- Desktop: `class="d-none d-md-flex"` (display only ≥960px)

## Features

### Mobile Navigation Drawer

**Appearance:**
- Slides from left side
- 280px width
- Temporary overlay (closes on navigation/click outside)
- Material Design elevation
- Smooth slide animation (60fps)

**Contents:**
- App title at top
- Navigation items with icons
- Divider
- User menu at bottom (logout/login)

**Behavior:**
- Opens on hamburger click
- Closes on:
  - Navigation item click
  - Overlay click
  - Escape key press
  - Swipe gesture (Vuetify built-in)

### Desktop Navigation (Unchanged)

**Appearance:**
- Inline navigation buttons in AppBar
- Text + icon buttons
- User menu dropdown

**Behavior:**
- Direct click navigation
- No drawer on desktop

## Implementation Steps

### Step 1: Create Navigation Config (30 min)

**File:** `frontend/src/config/navigationItems.js`

```javascript
export const navigationItems = [
  {
    icon: 'mdi-home',
    label: 'Home',
    route: '/',
    requiresAuth: false
  },
  {
    icon: 'mdi-account-multiple',
    label: 'Phenopackets',
    route: '/phenopackets',
    requiresAuth: true
  },
  {
    icon: 'mdi-dna',
    label: 'Variants',
    route: '/variants',
    requiresAuth: true
  },
  {
    icon: 'mdi-book-open-variant',
    label: 'Publications',
    route: '/publications',
    requiresAuth: true
  },
  {
    icon: 'mdi-chart-bar',
    label: 'Aggregations',
    route: '/aggregations',
    requiresAuth: true
  }
];
```

### Step 2: Create MobileDrawer Component (1 hour)

**File:** `frontend/src/components/MobileDrawer.vue`

- Vuetify v-navigation-drawer
- Import navigationItems
- Filter by authentication status
- Add toggle() method
- Add logout functionality

### Step 3: Update AppBar Component (1 hour)

**Changes:**
1. Import navigationItems config
2. Add hamburger icon with `@click="toggleDrawer"`
3. Add `d-md-none` class to hamburger (mobile only)
4. Add `d-none d-md-flex` to desktop nav (desktop only)
5. Emit `toggle-drawer` event
6. Replace hardcoded nav items with config

### Step 4: Update App.vue (30 min)

**Changes:**
1. Import MobileDrawer component
2. Add `<MobileDrawer ref="mobileDrawer" />`
3. Wire up AppBar toggle event: `@toggle-drawer="$refs.mobileDrawer.toggle()"`

### Step 5: Update Vuetify (15 min)

```bash
cd frontend
npm install vuetify@^3.10.6
npm update
```

### Step 6: Add Auth Helper (Optional) (30 min)

**File:** `frontend/src/utils/auth.js`

- Add `getCurrentUser()` helper
- Decode JWT token for user info
- Return username and expiration

### Step 7: Testing (1 hour)

**Mobile Testing (<960px):**
- [ ] Hamburger icon visible in AppBar
- [ ] Clicking hamburger opens drawer
- [ ] Drawer shows all navigation items with icons
- [ ] Clicking nav item navigates and closes drawer
- [ ] Clicking overlay closes drawer
- [ ] Escape key closes drawer
- [ ] Swipe gesture closes drawer
- [ ] User menu (login/logout) works

**Desktop Testing (≥960px):**
- [ ] Hamburger icon hidden
- [ ] Inline navigation buttons visible
- [ ] Navigation works as before
- [ ] User menu dropdown works

**Accessibility:**
- [ ] Tab key navigates through drawer items
- [ ] Escape key closes drawer
- [ ] ARIA labels present on buttons
- [ ] Screen reader announces drawer open/close

**Cross-Browser:**
- [ ] Chrome (mobile + desktop)
- [ ] Firefox (mobile + desktop)
- [ ] Safari (iOS + macOS)
- [ ] Edge (mobile + desktop)

## Acceptance Criteria

### Functionality
- [ ] Mobile users (<960px) see hamburger menu icon in AppBar
- [ ] Clicking hamburger opens navigation drawer from left
- [ ] Drawer contains all navigation items with icons
- [ ] Drawer closes after clicking navigation item
- [ ] Drawer closes when clicking overlay (outside drawer)
- [ ] Drawer closes on Escape key press
- [ ] Desktop users (≥960px) see inline navigation buttons (unchanged)
- [ ] User menu works in both mobile and desktop modes
- [ ] Authentication-required routes hidden when not logged in

### User Experience
- [ ] Smooth drawer animation (60fps, no jank)
- [ ] Drawer width appropriate for mobile (280px)
- [ ] Navigation items easily tappable (44px min touch target)
- [ ] Visual feedback on hover/focus
- [ ] Material Design elevation on drawer

### Accessibility
- [ ] Tab key navigates through drawer items
- [ ] Escape key closes drawer
- [ ] ARIA labels on hamburger icon
- [ ] Screen reader announces drawer state
- [ ] Keyboard-only navigation works

### Code Quality
- [ ] DRY principle - single source of truth for nav items
- [ ] Options API pattern (not Composition API)
- [ ] ESLint passes with no warnings
- [ ] No console errors or warnings
- [ ] Follows existing project conventions

### Performance
- [ ] No layout shift when drawer opens/closes
- [ ] Smooth animations (60fps)
- [ ] No performance degradation on mobile devices
- [ ] Fast first paint (<2s on 3G)

## Files Created/Modified

### New Files (2):
- `frontend/src/config/navigationItems.js` (~30 lines)
- `frontend/src/components/MobileDrawer.vue` (~90 lines)

**Total new code:** ~120 lines

### Modified Files (3):
- `frontend/src/components/AppBar.vue` (~40 lines changed)
  - Add hamburger icon
  - Add responsive classes (d-md-none, d-none d-md-flex)
  - Replace hardcoded nav with config import
  - Add toggle-drawer event
- `frontend/src/App.vue` (~10 lines changed)
  - Import MobileDrawer component
  - Add MobileDrawer to template
  - Wire up toggle event
- `frontend/src/utils/auth.js` (~15 lines added)
  - Add getCurrentUser() helper (optional)

### Dependencies Updated:
- `frontend/package.json` (Vuetify 3.8.12 → 3.10.6)

**Total modified:** ~65 lines

**Grand Total:** ~185 lines (new + modified)

## Dependencies

**Blocked by:** None - independent feature

**Blocks:** None

**Requires:**
- Vuetify 3.10.6+ (updated from 3.8.12)
- Vue Router 4.x (already present)
- Existing auth.js utilities

## Timeline

**Estimated:** 5 hours (1 day)

**Breakdown:**
- Step 1 (Navigation Config): 0.5 hours
- Step 2 (MobileDrawer Component): 1 hour
- Step 3 (Update AppBar): 1 hour
- Step 4 (Update App.vue): 0.5 hours
- Step 5 (Update Vuetify): 0.25 hours
- Step 6 (Auth Helper): 0.5 hours
- Step 7 (Testing): 1.25 hours

**Total:** 5 hours

## Priority

**P1 (High)** - User experience / mobile accessibility

**Rationale:**
- Mobile users cannot currently navigate the site
- Poor user experience on mobile devices
- Responsive design is a baseline requirement
- Quick win (5 hours) with high impact

**Recommended Timeline:** Implement before Issue #37 Phase 2

## Labels

`frontend`, `mobile`, `navigation`, `responsive`, `vuetify`, `p1`, `ux`

## Reference Documentation

Full implementation plan: [`docs/frontend/NAVIGATION-MODERNIZATION-PLAN.md`](https://github.com/berntpopp/hnf1b-db/blob/main/docs/frontend/NAVIGATION-MODERNIZATION-PLAN.md)

## Testing Verification

### Manual Test Plan

**Test 1: Mobile Hamburger Menu**
```
1. Resize browser to <960px width
2. Verify hamburger icon (☰) visible in AppBar
3. Click hamburger icon
4. Verify drawer slides in from left
5. Verify all navigation items present with icons
6. Click a navigation item
7. Verify navigation occurs
8. Verify drawer closes automatically
```

**Test 2: Drawer Overlay Close**
```
1. Open mobile drawer (hamburger menu)
2. Click on the dimmed overlay (outside drawer)
3. Verify drawer closes
4. No navigation should occur
```

**Test 3: Escape Key**
```
1. Open mobile drawer
2. Press Escape key
3. Verify drawer closes immediately
4. No other side effects
```

**Test 4: Desktop Navigation Unchanged**
```
1. Resize browser to ≥960px width
2. Verify hamburger icon NOT visible
3. Verify inline navigation buttons visible in AppBar
4. Click navigation buttons
5. Verify navigation works as before
6. Verify no drawer behavior on desktop
```

**Test 5: Authentication Filtering**
```
1. Logout (if logged in)
2. Open mobile drawer
3. Verify only Home and Login visible
4. Login
5. Open mobile drawer
6. Verify all nav items now visible (Phenopackets, Variants, etc.)
```

**Test 6: User Menu Mobile**
```
1. Login
2. Open mobile drawer on mobile (<960px)
3. Verify Logout button at bottom of drawer
4. Click Logout
5. Verify logout occurs
6. Verify drawer closes
7. Verify redirected to /login
```

**Test 7: Accessibility (Keyboard)**
```
1. Open mobile drawer
2. Press Tab repeatedly
3. Verify focus moves through drawer items
4. Press Enter on focused item
5. Verify navigation occurs
6. Press Escape with drawer open
7. Verify drawer closes
```

**Test 8: Touch Gestures**
```
1. On actual mobile device (or Chrome DevTools device mode)
2. Open drawer
3. Swipe left on drawer
4. Verify drawer closes
5. Open drawer again
6. Swipe right on overlay
7. Verify drawer stays open (only swipe left closes)
```

## Known Limitations

1. **No Nested Menus:**
   - Current design is flat navigation only
   - No sub-menus or dropdowns in drawer
   - Consider adding in future if needed

2. **No Swipe-to-Open:**
   - Drawer only opens via hamburger click
   - No edge swipe gesture to open
   - Vuetify supports this, could add in Phase 2

3. **No Persistent Drawer:**
   - Always temporary (overlay mode)
   - Could add persistent/mini variant for tablets in future

4. **No Dark Mode Toggle:**
   - Dark mode toggle not included in drawer
   - Consider adding in future navigation enhancement

## Future Enhancements (Not in Scope)

- [ ] Swipe-from-edge gesture to open drawer
- [ ] Persistent drawer mode for tablets (960-1280px)
- [ ] Mini drawer variant (collapsed with icons only)
- [ ] Nested navigation (sub-menus)
- [ ] Dark mode toggle in drawer
- [ ] Breadcrumb navigation
- [ ] Search bar in drawer
- [ ] Recent pages history
- [ ] Favorites/bookmarks

## Rollback Strategy

If issues arise:

1. **Remove MobileDrawer Component:**
   ```vue
   <!-- App.vue - remove: -->
   <!-- <MobileDrawer ref="mobileDrawer" /> -->
   ```

2. **Remove Hamburger Icon:**
   ```vue
   <!-- AppBar.vue - remove: -->
   <!-- <v-app-bar-nav-icon ... /> -->
   ```

3. **Revert Responsive Classes:**
   ```vue
   <!-- AppBar.vue - remove classes: -->
   <!-- d-md-none, d-none d-md-flex -->
   ```

4. **Revert Vuetify (if needed):**
   ```bash
   npm install vuetify@3.8.12
   ```

**Impact:** Minimal - reverts to desktop-only navigation (current state).

## Security Considerations

### Authentication
- Navigation items filtered by auth status
- Token checked before showing protected routes
- Logout properly clears localStorage
- No sensitive data exposed in drawer

### XSS Prevention
- All navigation labels from trusted config
- No user-generated content in drawer
- Router guards still enforce auth requirements

## Performance Considerations

### Bundle Size
- MobileDrawer component: ~3KB gzipped
- navigationItems config: <1KB
- Vuetify drawer components already in bundle
- **Total impact:** Negligible (<5KB)

### Runtime Performance
- Drawer only rendered when opened (v-if or lazy)
- No performance impact when closed
- Smooth 60fps animations on modern devices
- Touch events properly throttled

### Mobile Data Usage
- No additional network requests
- No images loaded for navigation
- Icons from Material Design Icons (already in bundle)
- **Impact:** Zero additional data usage

## Design Mockups

### Mobile View (<960px)

```
┌──────────────────────────────┐
│ ☰  HNF1B Database    [👤]    │ ← AppBar with hamburger
└──────────────────────────────┘
│                              │
│    Page Content              │
│                              │
└──────────────────────────────┘
```

**After clicking hamburger:**

```
┌──────────────────────────────┐
│ ☰  HNF1B Database    [👤]    │
└──────────────────────────────┘
│░░░░░░░░░░░░│                 │ ← Overlay (dimmed)
│ HNF1B DB   │                 │
│────────────│                 │
│ 🏠 Home    │  Page Content   │ ← Drawer (280px)
│ 👥 Pheno   │                 │
│ 🧬 Variants│                 │
│ 📚 Pubs    │                 │
│ 📊 Charts  │                 │
│────────────│                 │
│ 🚪 Logout  │                 │
└────────────┴─────────────────┘
```

### Desktop View (≥960px)

```
┌────────────────────────────────────────────────────┐
│ HNF1B Database  🏠Home 👥Pheno 🧬Var 📚Pubs  [👤] │ ← Inline nav
└────────────────────────────────────────────────────┘
│                                                    │
│              Page Content                          │
│                                                    │
└────────────────────────────────────────────────────┘
```

(No hamburger, no drawer - existing desktop navigation unchanged)
