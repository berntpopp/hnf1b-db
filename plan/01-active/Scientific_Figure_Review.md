# Scientific Figure Review & Data Visualization Audit

## Executive Summary

The data visualization suite in HNF1B-db is technically sophisticated, leveraging **D3.js** for custom visualizations and **Chart.js** for standard time-series. The implementation of specific scientific plots like **Kaplan-Meier survival curves** and **Variant-Phenotype comparisons** approaches publication quality.

However, several visualizations suffer from **classic scientific design pitfalls**: usage of colorblind-unsafe palettes (Red/Green), redundant data-ink (100% stacked bars for binary outcomes), and use of donut charts for complex distributions.

**Overall Scientific Rating: 8.0/10**

---

## Detailed Figure Analysis

### 1. Donut Chart (Demographics/Aggregations)
**Rating: 6/10**

*   **Critique:**
    *   **Visual Perception:** Donut charts are notoriously difficult for human perception when comparing arc lengths or areas, especially with >5 categories.
    *   **Legend:** The separated legend forces the eye to travel back and forth, increasing cognitive load.
    *   **Precision:** Use of percentages is good, but sorting is inconsistent in some aggregation modes.

*   **Scientific Recommendations:**
    *   **Switch to Horizontal Bar Chart:** This allows for easy comparison of lengths and accommodates long labels (common in medical ontologies).
    *   **Sort Data:** Always sort bars/segments by value (descending) unless there is an intrinsic order (e.g., Age Groups).

### 2. Stacked Bar Chart (Phenotypic Features)
**Rating: 8/10**

*   **Critique:**
    *   **Strengths:** Effectively communicates the "missing data problem" inherent in clinical datasets (Present vs. Absent vs. Not Reported).
    *   **Accessibility Failure:** The default palette uses `#4CAF50` (Green) and `#F44336` (Red). This is indistinguishable for ~5% of male users (Deuteranopia).
    *   **Data-Ink:** The "Not Reported" section often dominates, compressing the "Present" signal which is scientifically most interesting.

*   **Scientific Recommendations:**
    *   **Color Palette:** Adopt a colorblind-safe palette.
        *   *Suggestion:* **Blue** (Present), **Orange** (Absent), **Light Gray** (Not Reported). (IBM Design Language / Okabe-Ito).
    *   **Normalization:** Consider an option to normalize only on *observed* cases (Present + Absent = 100%) to better show true penetrance.

### 3. Publications Timeline
**Rating: 7/10**

*   **Critique:**
    *   **Strengths:** "Cumulative" mode is excellent for showing field growth.
    *   **Clutter:** The "Annual" view with multiple categories results in a "spaghetti plot" with many crossing lines, making it hard to trace individual trends.
    *   **Fill:** Lines are unfilled, making the volume of research hard to estimate visually.

*   **Scientific Recommendations:**
    *   **Stacked Area Chart:** For the "Cumulative" view, use a Stacked Area chart. This emphasizes the total volume while showing composition.
    *   **Small Multiples:** If comparing distinct trends is important, split into small faceted plots (e.g., Case Reports vs. Research).

### 4. Variant Comparison Chart
**Rating: 9/10**

*   **Critique:**
    *   **Strengths:** Excellent "mirrored" design allows direct comparison of two cohorts. Statistical annotations (FDR p-values) are crucial for scientific validity.
    *   **Redundancy:** Stacked "Yes/No" bars to 100% are visually redundant. The "No" bar adds no new information if the axis is "Prevalence (%)".
    *   **Uncertainty:** Lacks Error Bars (95% Confidence Intervals). In scientific figures, point estimates of prevalence without error bars are potentially misleading, especially for rare phenotypes.

*   **Scientific Recommendations:**
    *   **Simplify:** Remove the "Absent" (No) bar. Show two side-by-side bars (Group 1 vs Group 2) for "Present" only.
    *   **Add Error Bars:** Implement Wilson Score Interval or similar to show 95% CI on the prevalence bars.
    *   **Diagonal Labeling:** Good handling of p-values for tight spaces.

### 5. Kaplan-Meier Survival Curves
**Rating: 9.5/10**

*   **Critique:**
    *   **Strengths:** Gold-standard implementation. Includes confidence bands (shaded), sensory markers (ticks), and median survival lines. This is ready for a manuscript.
    *   **Missing Standard:** Oncology/Genetics papers typically require a "Number at Risk" table aligned below the X-axis.

*   **Scientific Recommendations:**
    *   **Risk Table:** Implement a `<table>` below the SVG that aligns with the X-axis ticks, showing the count of patients at risk at each timepoint.

### 6. DNA Distance Analysis
**Rating: 8.5/10**

*   **Critique:**
    *   **Strengths:** Box plots are the correct choice for comparing distributions. Statistical rigor (Mann-Whitney U) is present.
    *   **Data Density:** A simple box plot hides the sample size `n`.
    
*   **Scientific Recommendations:**
    *   **Jitter Points:** Overlay individual data points (with partial transparency) on top of the box plots. This proves that the distribution is real and not an artifact of small sample size.

---

## Action Plan for Improvement

1.  **Immediate Fix (High Impact):** Change the **Red/Green** color scheme in `StackedBarChart.vue` and `VariantComparisonChart.vue` to **Blue/Orange** (Colorblind Safe).
2.  **Visualization Upgrade:** Update `VariantComparisonChart.vue` to remove the "Absent" stack and add **95% Confidence Interval Error Bars**.
3.  **Enhancement:** Refactor `DonutChart.vue` to optional `HorizontalBarChart.vue` for better readability of HPO terms.
