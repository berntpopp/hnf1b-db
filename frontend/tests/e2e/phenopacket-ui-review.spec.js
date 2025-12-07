// @ts-check
import { test } from '@playwright/test';

/**
 * Phenopacket Page UI/UX Review Test Suite
 *
 * Takes screenshots of multiple phenopacket pages for visual review
 * and collects accessibility audit data.
 */

const PHENOPACKET_IDS = ['phenopacket-415', 'phenopacket-502', 'phenopacket-22', 'phenopacket-100'];

test.describe('Phenopacket Page UI Review', () => {
  test('capture multiple phenopacket pages for UI analysis', async ({ page }) => {
    const screenshots = [];

    for (const id of PHENOPACKET_IDS) {
      console.log(`\n=== Capturing ${id} ===`);

      // Navigate to phenopacket page
      await page.goto(`http://localhost:5173/phenopackets/${id}`, {
        waitUntil: 'networkidle',
        timeout: 30000,
      });

      // Wait for content to load
      await page.waitForTimeout(2000);

      // Check if page loaded successfully
      const errorAlert = await page.locator('.v-alert[type="error"]').first();
      const hasError = await errorAlert.isVisible().catch(() => false);

      if (hasError) {
        console.log(`  ❌ ${id}: Page has error, skipping`);
        continue;
      }

      // Capture full page screenshot
      const screenshotPath = `test-results/${id}-full.png`;
      await page.screenshot({
        path: screenshotPath,
        fullPage: true,
      });
      console.log(`  ✓ Screenshot saved: ${screenshotPath}`);

      // Collect page metrics
      const metrics = await page.evaluate(() => {
        const statsCards = document.querySelectorAll('.v-col.cols-6.sm-3 .v-card');
        const tabs = document.querySelectorAll('.v-tabs .v-tab');
        const heroSection = document.querySelector('.hero-section');
        const contentCards = document.querySelectorAll('.v-tabs-window-item .v-card');

        return {
          statsCardsCount: statsCards.length,
          tabsCount: tabs.length,
          hasHeroSection: !!heroSection,
          heroHeight: heroSection?.getBoundingClientRect().height || 0,
          contentCardsCount: contentCards.length,
          viewportHeight: window.innerHeight,
          pageHeight: document.body.scrollHeight,
          scrollRequired: document.body.scrollHeight > window.innerHeight,
        };
      });

      console.log(`  Metrics: ${JSON.stringify(metrics, null, 2)}`);
      screenshots.push({ id, path: screenshotPath, metrics });
    }

    console.log('\n=== Summary ===');
    console.log(`Captured ${screenshots.length} screenshots`);

    // Generate analysis report
    const report = {
      timestamp: new Date().toISOString(),
      screenshots: screenshots,
      analysis: {
        heroSectionConsistency: screenshots.every((s) => s.metrics?.hasHeroSection),
        statsCardsConsistency: screenshots.every((s) => s.metrics?.statsCardsCount === 4),
        avgHeroHeight:
          screenshots.reduce((sum, s) => sum + (s.metrics?.heroHeight || 0), 0) /
          screenshots.length,
        avgPageHeight:
          screenshots.reduce((sum, s) => sum + (s.metrics?.pageHeight || 0), 0) /
          screenshots.length,
      },
    };

    console.log('Analysis:', JSON.stringify(report.analysis, null, 2));
  });

  test('accessibility audit for phenopacket page', async ({ page }) => {
    // Navigate to a representative phenopacket page
    await page.goto('http://localhost:5173/phenopackets/phenopacket-415', {
      waitUntil: 'networkidle',
      timeout: 30000,
    });

    await page.waitForTimeout(2000);

    // Check for key accessibility attributes
    const accessibilityChecks = await page.evaluate(() => {
      const checks = [];

      // Check buttons have aria-labels
      const buttons = document.querySelectorAll('button');
      const buttonsWithoutLabel = Array.from(buttons).filter(
        (btn) =>
          !btn.getAttribute('aria-label') &&
          !btn.textContent?.trim() &&
          !btn.querySelector('.mdi')?.getAttribute('aria-hidden')
      );
      checks.push({
        name: 'Buttons with accessible labels',
        passed: buttonsWithoutLabel.length === 0,
        count: buttons.length,
        issues: buttonsWithoutLabel.length,
      });

      // Check icons are decorative (aria-hidden)
      const icons = document.querySelectorAll('.mdi, .v-icon');
      const iconsWithoutAriaHidden = Array.from(icons).filter(
        (icon) => !icon.getAttribute('aria-hidden')
      );
      checks.push({
        name: 'Icons marked as decorative',
        passed: iconsWithoutAriaHidden.length < icons.length * 0.5, // Allow 50% tolerance
        count: icons.length,
        issues: iconsWithoutAriaHidden.length,
      });

      // Check headings hierarchy
      const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
      checks.push({
        name: 'Heading structure',
        passed: headings.length > 0,
        count: headings.length,
        details: Array.from(headings).map(
          (h) => `${h.tagName}: ${h.textContent?.substring(0, 30)}...`
        ),
      });

      // Check color contrast (simplified check for text visibility)
      const statsCards = document.querySelectorAll('.v-col .v-card');
      checks.push({
        name: 'Stats cards present',
        passed: statsCards.length >= 4,
        count: statsCards.length,
      });

      // Check tab navigation
      const tabs = document.querySelectorAll('[role="tab"], .v-tab');
      const tabsWithLabel = Array.from(tabs).filter(
        (tab) => tab.getAttribute('aria-label') || tab.textContent?.trim()
      );
      checks.push({
        name: 'Tabs are navigable',
        passed: tabsWithLabel.length === tabs.length,
        count: tabs.length,
        issues: tabs.length - tabsWithLabel.length,
      });

      return checks;
    });

    console.log('\n=== Accessibility Audit Results ===');
    for (const check of accessibilityChecks) {
      const status = check.passed ? '✓' : '✗';
      console.log(
        `${status} ${check.name}: ${check.count} elements${check.issues ? `, ${check.issues} issues` : ''}`
      );
      if (check.details) {
        check.details.forEach((d) => console.log(`    - ${d}`));
      }
    }

    // Take accessibility-focused screenshot
    await page.screenshot({
      path: 'test-results/accessibility-audit.png',
      fullPage: true,
    });
  });

  test('layout density analysis', async ({ page }) => {
    await page.goto('http://localhost:5173/phenopackets/phenopacket-415', {
      waitUntil: 'networkidle',
      timeout: 30000,
    });

    await page.waitForTimeout(2000);

    // Analyze layout metrics
    const layoutAnalysis = await page.evaluate(() => {
      const viewport = {
        width: window.innerWidth,
        height: window.innerHeight,
      };

      // Hero section analysis
      const hero = document.querySelector('.hero-section');
      const heroRect = hero?.getBoundingClientRect();

      // Stats cards analysis
      const statsRow = document.querySelector('.hero-section .v-row:last-child');
      const statsRect = statsRow?.getBoundingClientRect();

      // Main content analysis
      const mainContent = document.querySelector('.v-card.border-opacity-12');
      const mainRect = mainContent?.getBoundingClientRect();

      // Whitespace calculation
      const heroWhitespace = heroRect ? heroRect.height - (statsRect?.height || 0) : 0;

      // Compute content density
      const totalContentHeight = (heroRect?.height || 0) + (mainRect?.height || 0);
      const _visibleContentRatio = Math.min(1, viewport.height / totalContentHeight);

      return {
        viewport,
        hero: {
          height: heroRect?.height || 0,
          width: heroRect?.width || 0,
          whitespace: heroWhitespace,
          percentOfViewport: heroRect ? ((heroRect.height / viewport.height) * 100).toFixed(1) : 0,
        },
        stats: {
          height: statsRect?.height || 0,
          cardsVisible: document.querySelectorAll('.hero-section .v-card').length,
        },
        mainContent: {
          height: mainRect?.height || 0,
          topOffset: mainRect?.top || 0,
          immediatelyVisible: mainRect ? mainRect.top < viewport.height : false,
        },
        recommendations: [],
      };
    });

    // Add recommendations based on analysis
    if (layoutAnalysis.hero.percentOfViewport > 40) {
      layoutAnalysis.recommendations.push(
        `Hero section uses ${layoutAnalysis.hero.percentOfViewport}% of viewport - consider reducing padding`
      );
    }

    if (!layoutAnalysis.mainContent.immediatelyVisible) {
      layoutAnalysis.recommendations.push(
        'Main content tabs require scrolling to see - consider more compact hero'
      );
    }

    if (layoutAnalysis.hero.whitespace > 50) {
      layoutAnalysis.recommendations.push(
        `${layoutAnalysis.hero.whitespace}px of vertical whitespace in hero - optimize spacing`
      );
    }

    console.log('\n=== Layout Density Analysis ===');
    console.log(JSON.stringify(layoutAnalysis, null, 2));

    // Take a screenshot with annotations overlay
    await page.screenshot({
      path: 'test-results/layout-analysis.png',
      fullPage: true,
    });
  });
});
