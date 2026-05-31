/**
 * Parse ACMG/AMP and ClinGen-CNV classification-criteria strings into
 * structured, render-ready data, plus chip-color helpers and description maps.
 *
 * Data formats (verified against the live database):
 *   ACMG:         "PM1_Moderate, PM2_Supporting, PS2_Strong"   (CODE_Strength, comma-separated)
 *   ClinGen CNV:  "1A, 2A, 3A, 4Cx1(0.15), 4Lx1(0.15)"          (section[xCount](points))
 *
 * Source: variantInterpretation.extensions[name='classification_criteria'].value
 * Pure module, no I/O.
 */

// Full ACMG/AMP 2015 (Richards et al.) criterion → short plain-English meaning.
export const ACMG_CRITERIA = {
  // Pathogenic
  PVS1: 'Null variant in a gene where loss of function is a known mechanism',
  PS1: 'Same amino-acid change as an established pathogenic variant',
  PS2: 'De novo (maternity and paternity confirmed)',
  PS3: 'Well-established functional studies show a damaging effect',
  PS4: 'Prevalence in affected individuals significantly increased vs controls',
  PM1: 'Located in a mutational hotspot / critical functional domain',
  PM2: 'Absent or at extremely low frequency in population databases',
  PM3: 'For recessive disorders, detected in trans with a pathogenic variant',
  PM4: 'Protein length change (in-frame indel / stop-loss) in a non-repeat region',
  PM5: 'Novel missense at a residue where a different pathogenic missense is known',
  PM6: 'Assumed de novo (without confirmation of parentage)',
  PP1: 'Cosegregation with disease in multiple affected family members',
  PP2: 'Missense in a gene with a low rate of benign missense variation',
  PP3: 'Multiple computational lines of evidence support a damaging effect',
  PP4: "Patient's phenotype/family history highly specific for the gene",
  PP5: 'Reputable source reports the variant as pathogenic',
  // Benign
  BA1: 'Allele frequency >5% in population databases (stand-alone benign)',
  BS1: 'Allele frequency greater than expected for the disorder',
  BS2: 'Observed in a healthy adult for a fully-penetrant early-onset disorder',
  BS3: 'Well-established functional studies show no damaging effect',
  BS4: 'Lack of segregation in affected family members',
  BP1: 'Missense in a gene where only truncating variants cause disease',
  BP2: 'Observed in trans/in cis with a pathogenic variant',
  BP3: 'In-frame indel in a repetitive region without known function',
  BP4: 'Multiple computational lines of evidence suggest no impact',
  BP5: 'Found in a case with an alternate molecular basis for disease',
  BP6: 'Reputable source reports the variant as benign',
  BP7: 'Synonymous variant with no predicted splice impact',
};

// ClinGen CNV (Riggs et al. 2020) scoring sections → short meaning. Starter map;
// unknown sections degrade to a code-only chip.
export const CLINGEN_CNV_SECTIONS = {
  '1A': 'Section 1: contains protein-coding or other functional elements',
  '1B': 'Section 1: no protein-coding or functional elements',
  '2A': 'Section 2: overlaps an established dosage-sensitive (HI/TS) gene or region',
  '3A': 'Section 3: 0–24 protein-coding genes',
  '3B': 'Section 3: 25–34 protein-coding genes',
  '3C': 'Section 3: 35+ protein-coding genes',
  '4C': 'Section 4: case evidence (literature / case-level data)',
  '4L': 'Section 4: case–control / observational evidence',
  '5A': 'Section 5: inheritance / family-history evidence',
};

/**
 * @param {string|null} criteria  comma-separated criteria string
 * @param {string|null} guidelines  "ACMG" | "ClinGen CNV" (defaults to ACMG)
 * @returns {{guideline:string, pathogenic:Array, benign:Array, cnv:Array, totalPoints:(number|null), raw:string}}
 */
export function parseClassificationCriteria(criteria, guidelines) {
  const raw = typeof criteria === 'string' ? criteria.trim() : '';
  const guideline = guidelines === 'ClinGen CNV' ? 'ClinGen CNV' : 'ACMG';
  const result = { guideline, pathogenic: [], benign: [], cnv: [], totalPoints: null, raw };
  if (!raw) return result;

  const tokens = raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);

  if (guideline === 'ClinGen CNV') {
    let total = 0;
    let sawPoints = false;
    for (const tok of tokens) {
      const m = tok.match(/^([0-9]+[A-Za-z]+)(?:x(\d+))?(?:\(([-\d.]+)\))?$/);
      const section = m ? m[1].toUpperCase() : tok;
      const count = m && m[2] ? parseInt(m[2], 10) : 1;
      let points = null;
      if (m && m[3] != null) {
        const p = parseFloat(m[3]);
        if (!Number.isNaN(p)) {
          points = p;
          total += p; // parenthesized value is the section TOTAL (already x count)
          sawPoints = true;
        }
      }
      result.cnv.push({ section, count, points, label: CLINGEN_CNV_SECTIONS[section] || '' });
    }
    result.totalPoints = sawPoints ? Math.round(total * 100) / 100 : null;
    return result;
  }

  // ACMG
  for (const tok of tokens) {
    const us = tok.indexOf('_');
    const code = us === -1 ? tok : tok.slice(0, us);
    const strength = us === -1 ? '' : tok.slice(us + 1);
    const direction = /^B/i.test(code) ? 'benign' : 'pathogenic';
    const entry = { code, strength, direction, label: ACMG_CRITERIA[code] || '' };
    (direction === 'benign' ? result.benign : result.pathogenic).push(entry);
  }
  return result;
}

/** Vuetify color for an ACMG criterion chip. */
export function acmgChipColor({ direction, strength } = {}) {
  if (direction === 'benign') {
    return strength === 'Supporting' ? 'green-lighten-1' : 'green';
  }
  if (strength === 'VeryStrong' || strength === 'Strong') return 'red';
  if (strength === 'Moderate') return 'deep-orange';
  return 'orange';
}

/** Vuetify color for a ClinGen-CNV section chip, by point sign. */
export function cnvChipColor(points) {
  if (points == null || Number.isNaN(points)) return 'grey';
  return points >= 0 ? 'orange' : 'green';
}
