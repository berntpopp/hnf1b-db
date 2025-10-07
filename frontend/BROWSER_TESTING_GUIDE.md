# Browser Testing Guide - Issue #31

## Test Environment Setup

**Services Running:**
- ✅ Backend: `http://localhost:8000`
- ✅ Frontend: `http://localhost:5173`

**Open Frontend:** Navigate to `http://localhost:5173` in your browser

---

## Test Checklist

### 1. Initial Page Load (5 tests)

#### Test 1.1: Navigate to Phenopackets Page
- [ ] Click "Phenopackets" in navigation menu
- [ ] **Expected:** URL changes to `http://localhost:5173/phenopackets`
- [ ] **Expected:** Page loads successfully (no white screen)

#### Test 1.2: Loading Spinner
- [ ] Refresh the page (F5)
- [ ] **Expected:** See loading spinner briefly during data fetch
- [ ] **Expected:** Spinner disappears when data loads

#### Test 1.3: Table Displays Data
- [ ] **Expected:** Table shows at least 10 rows (or fewer if less data)
- [ ] **Expected:** Table has 6 columns:
  - Phenopacket ID
  - Subject ID
  - Sex
  - Primary Disease
  - Features
  - Variants

#### Test 1.4: Data Formatting
- [ ] **Expected:** Phenopacket IDs are lime-colored chips with document icon
- [ ] **Expected:** Sex column shows icons:
  - 🔵 Male (blue icon)
  - 🩷 Female (pink icon)
  - ⚪ Unknown (grey help icon)
- [ ] **Expected:** Features/Variants show as colored badges (green/blue if >0, grey if 0)

#### Test 1.5: Performance - First Load
- [ ] Open browser DevTools (F12) → Network tab
- [ ] Refresh page (F5)
- [ ] Check "Load" time in Network tab
- [ ] **Expected:** Total page load < 500ms
- [ ] **Expected:** Single API call to `/api/v2/phenopackets/?skip=0&limit=10`

---

### 2. Browser Console Check (2 tests)

#### Test 2.1: No Console Errors
- [ ] Open DevTools (F12) → Console tab
- [ ] Refresh page (F5)
- [ ] **Expected:** No red error messages
- [ ] **Expected:** No 404 errors
- [ ] **Expected:** No CORS errors

#### Test 2.2: Deprecation Warnings (Optional)
- [ ] Check console for any warnings
- [ ] **Note:** Yellow warnings are acceptable, red errors are not

---

### 3. Pagination Testing (6 tests)

#### Test 3.1: Next Page Button
- [ ] Click "Next" arrow button (➡️)
- [ ] **Expected:** URL stays the same (`/phenopackets`)
- [ ] **Expected:** Table loads next 10 records
- [ ] **Expected:** Page indicator updates (e.g., "11-20 of 20")
- [ ] **Expected:** Animation < 300ms (feels instant)

#### Test 3.2: Previous Page Button
- [ ] Click "Previous" arrow button (⬅️)
- [ ] **Expected:** Returns to page 1
- [ ] **Expected:** Shows records 1-10

#### Test 3.3: First/Last Page Buttons
- [ ] Click "Last" button (⏭️)
- [ ] **Expected:** Jumps to last page
- [ ] Click "First" button (⏮️)
- [ ] **Expected:** Returns to first page

#### Test 3.4: Change Rows Per Page
- [ ] Click "Rows per page" dropdown
- [ ] Select "20"
- [ ] **Expected:** Table now shows 20 rows
- [ ] **Expected:** Page indicator updates (e.g., "1-20 of 20")

#### Test 3.5: Disabled States
- [ ] Go to first page
- [ ] **Expected:** "Previous" and "First" buttons are disabled (greyed out)
- [ ] Go to last page
- [ ] **Expected:** "Next" and "Last" buttons are disabled (greyed out)

#### Test 3.6: Performance - Pagination
- [ ] Open DevTools → Network tab
- [ ] Click "Next" button
- [ ] Check request time
- [ ] **Expected:** API response < 300ms
- [ ] **Expected:** Smooth transition (no lag)

---

### 4. Data Display Testing (5 tests)

#### Test 4.1: Sex Icons and Colors
- [ ] Find a row with "Male"
- [ ] **Expected:** Blue male icon + "Male" text
- [ ] Find a row with "Female"
- [ ] **Expected:** Pink female icon + "Female" text
- [ ] Find a row with "Unknown"
- [ ] **Expected:** Grey help icon + "Unknown" text

#### Test 4.2: Primary Disease Tooltip
- [ ] Hover over a disease name
- [ ] **Expected:** Tooltip appears showing full disease name
- [ ] Move mouse away
- [ ] **Expected:** Tooltip disappears

#### Test 4.3: Features Count Badge
- [ ] Look at "Features" column
- [ ] **Expected:** If count > 0, badge is green
- [ ] **Expected:** If count = 0, badge is grey
- [ ] **Expected:** Number is clearly visible

#### Test 4.4: Variants Count Badge
- [ ] Look at "Variants" column
- [ ] **Expected:** If count > 0, badge is blue
- [ ] **Expected:** If count = 0, badge is grey

#### Test 4.5: Subject ID Display
- [ ] Check "Subject ID" column
- [ ] **Expected:** Shows patient IDs or "N/A" if missing
- [ ] **Expected:** Text is readable and not truncated

---

### 5. Navigation Testing (3 tests)

#### Test 5.1: Click Phenopacket ID
- [ ] Click on a phenopacket ID chip (e.g., "phenopacket-2")
- [ ] **Expected:** URL changes to `/phenopackets/phenopacket-2`
- [ ] **Expected:** Navigates to detail page (may show error if not implemented yet)

#### Test 5.2: Back Button
- [ ] Click browser back button
- [ ] **Expected:** Returns to `/phenopackets` list view
- [ ] **Expected:** Table shows same data as before

#### Test 5.3: Legacy Redirect
- [ ] Manually navigate to `http://localhost:5173/individuals`
- [ ] **Expected:** Automatically redirects to `/phenopackets`
- [ ] **Expected:** No 404 error

---

### 6. Responsive Design Testing (4 tests)

#### Test 6.1: Desktop View (1920x1080)
- [ ] Resize browser to full width
- [ ] **Expected:** All 6 columns visible
- [ ] **Expected:** No horizontal scrolling
- [ ] **Expected:** Text not truncated

#### Test 6.2: Tablet View (768px)
- [ ] Resize browser to ~768px width (or use DevTools device emulation)
- [ ] **Expected:** Table remains usable
- [ ] **Expected:** May have horizontal scroll (acceptable)
- [ ] **Expected:** Navigation menu still accessible

#### Test 6.3: Mobile View (375px)
- [ ] Resize browser to ~375px width (or use DevTools)
- [ ] **Expected:** Table may collapse or scroll
- [ ] **Expected:** Navigation menu converts to hamburger menu
- [ ] **Expected:** Pagination controls still work

#### Test 6.4: Zoom Testing
- [ ] Zoom in to 150% (Ctrl/Cmd + +)
- [ ] **Expected:** Layout doesn't break
- [ ] Zoom out to 75% (Ctrl/Cmd + -)
- [ ] **Expected:** Layout still usable

---

### 7. Edge Cases Testing (4 tests)

#### Test 7.1: Empty State
- [ ] If possible, clear all data or filter to get 0 results
- [ ] **Expected:** Shows "No phenopackets found."
- [ ] **Expected:** No errors in console

#### Test 7.2: Long Disease Names
- [ ] Find a row with a very long disease name
- [ ] **Expected:** Text truncates with ellipsis (...)
- [ ] Hover over it
- [ ] **Expected:** Tooltip shows full name

#### Test 7.3: Missing Data (N/A)
- [ ] Find rows with missing subject IDs
- [ ] **Expected:** Shows "N/A" in Subject ID column
- [ ] Find rows with no primary disease
- [ ] **Expected:** Shows "N/A" in Primary Disease column

#### Test 7.4: Fast Pagination Clicking
- [ ] Rapidly click "Next" button 5 times quickly
- [ ] **Expected:** Pagination works correctly
- [ ] **Expected:** No duplicate requests
- [ ] **Expected:** No UI freezing

---

### 8. Network Testing (2 tests)

#### Test 8.1: Network Tab Inspection
- [ ] Open DevTools → Network tab
- [ ] Refresh page
- [ ] **Expected:** Only 1 API call to `/api/v2/phenopackets/`
- [ ] **Expected:** Response status: 200 OK
- [ ] Click "Next" button
- [ ] **Expected:** New API call with `skip=10&limit=10`

#### Test 8.2: API Response Structure
- [ ] Open DevTools → Network tab → Click on API request
- [ ] Click "Preview" or "Response" tab
- [ ] **Expected:** Array of objects
- [ ] Each object has:
  - `id` (UUID)
  - `phenopacket_id` (string)
  - `phenopacket` (nested object with subject, diseases, etc.)
  - `created_at` (timestamp)

---

### 9. Performance Testing (2 tests)

#### Test 9.1: Lighthouse Audit
- [ ] Open DevTools → Lighthouse tab
- [ ] Click "Analyze page load"
- [ ] **Expected:** Performance score > 70
- [ ] **Expected:** No major accessibility issues

#### Test 9.2: Smooth Scrolling (if 100+ records)
- [ ] Set rows per page to 100
- [ ] Scroll down the table
- [ ] **Expected:** Smooth scrolling (no janky frames)
- [ ] **Expected:** No layout shifts

---

## Test Results Summary

Fill this out as you test:

| Category | Tests Passed | Tests Failed | Notes |
|----------|--------------|--------------|-------|
| Initial Load | __/5 | __/5 | |
| Console Check | __/2 | __/2 | |
| Pagination | __/6 | __/6 | |
| Data Display | __/5 | __/5 | |
| Navigation | __/3 | __/3 | |
| Responsive | __/4 | __/4 | |
| Edge Cases | __/4 | __/4 | |
| Network | __/2 | __/2 | |
| Performance | __/2 | __/2 | |
| **TOTAL** | __/33 | __/33 | |

---

## Troubleshooting

### Issue: "Cannot GET /phenopackets"
**Fix:** Make sure frontend dev server is running (`npm run dev`)

### Issue: API 404 errors
**Fix:** Make sure backend is running (`make server` in backend directory)

### Issue: CORS errors
**Fix:** Check backend CORS configuration allows `http://localhost:5173`

### Issue: White screen / blank page
**Fix:** Check browser console for errors, may be a component rendering issue

### Issue: Data not loading
**Fix:** Check Network tab for failed API requests

---

## Quick Test (1 minute)

If you're short on time, run this quick smoke test:

1. ✅ Navigate to `http://localhost:5173/phenopackets`
2. ✅ Table displays data (no errors)
3. ✅ Click "Next" button → loads next page
4. ✅ Click phenopacket ID → navigates to detail
5. ✅ Open console (F12) → no red errors

If all 5 pass, the migration is functional! ✅

---

## Report Issues

If any tests fail, note:
1. Which test failed
2. What you expected vs. what happened
3. Screenshot or error message
4. Browser and version (Chrome, Firefox, Safari)
