/**
 * SEO Meta Tags Composable
 *
 * Provides per-page dynamic meta tags for improved search engine discoverability.
 * Critical for making HNF1B mutations findable via Google search.
 *
 * @see https://unhead.unjs.io/usage/composables/use-seo-meta
 * @see https://schema.org/docs/meddocs.html
 */

import { useHead, useSeoMeta } from '@unhead/vue';
import { computed } from 'vue';

const BASE_URL = 'https://hnf1b.org';
const SITE_NAME = 'HNF1B Database';
const DEFAULT_IMAGE = `${BASE_URL}/HNF1B-db_logo.png`;

/**
 * Generate SEO meta tags for a variant/mutation page.
 * Optimized for researchers searching by HGVS notation, rsID, or protein change.
 *
 * @param {Object} variant - Variant data from API
 * @param {string} variant.variant_id - Unique variant identifier
 * @param {string} variant.hgvs_c - HGVS coding notation (e.g., c.544+1G>A)
 * @param {string} variant.hgvs_p - HGVS protein notation (e.g., p.Arg177Gln)
 * @param {string} variant.type - Variant type (SNV, CNV, etc.)
 * @param {string} variant.classification - ACMG classification
 * @param {number} variant.cadd_score - CADD deleteriousness score
 * @param {number} variant.gnomad_af - gnomAD allele frequency
 * @param {number} variant.individual_count - Number of affected individuals
 * @param {string} variant.consequence - VEP consequence (missense_variant, etc.)
 */
export function useVariantSeo(variant) {
  const variantRef = computed(() => variant.value || variant);

  // Build comprehensive title with multiple search terms
  const title = computed(() => {
    const v = variantRef.value;
    if (!v) return `Variant Details | ${SITE_NAME}`;

    // Include both coding and protein notation for maximum findability
    const parts = ['HNF1B'];
    if (v.hgvs_c) parts.push(v.hgvs_c);
    if (v.hgvs_p) parts.push(v.hgvs_p);

    return `${parts.join(' ')} - Variant Details | ${SITE_NAME}`;
  });

  // Build rich description with clinical context
  const description = computed(() => {
    const v = variantRef.value;
    if (!v)
      return 'HNF1B gene variant information including clinical significance and population data.';

    const parts = [];

    // Primary identifier
    if (v.hgvs_c) {
      parts.push(`HNF1B variant ${v.hgvs_c}`);
    }

    // Protein change (important for researchers)
    if (v.hgvs_p && v.hgvs_p !== 'p.?') {
      parts.push(`(${v.hgvs_p})`);
    }

    // Clinical classification
    if (v.classification) {
      const classMap = {
        pathogenic: 'Pathogenic',
        likely_pathogenic: 'Likely Pathogenic',
        uncertain_significance: 'VUS',
        likely_benign: 'Likely Benign',
        benign: 'Benign',
      };
      parts.push(`- ${classMap[v.classification] || v.classification}`);
    }

    // Consequence
    if (v.consequence) {
      const conseqMap = {
        missense_variant: 'missense',
        nonsense_variant: 'nonsense',
        frameshift_variant: 'frameshift',
        splice_donor_variant: 'splice donor',
        splice_acceptor_variant: 'splice acceptor',
        synonymous_variant: 'synonymous',
        stop_gained: 'stop gain',
        start_lost: 'start loss',
      };
      const shortConseq = conseqMap[v.consequence] || v.consequence?.replace(/_/g, ' ');
      if (shortConseq) parts.push(`(${shortConseq})`);
    }

    // Clinical data
    if (v.individual_count && v.individual_count > 0) {
      parts.push(
        `Found in ${v.individual_count} individual${v.individual_count > 1 ? 's' : ''} with RCAD/MODY5.`
      );
    }

    // Scores
    const scores = [];
    if (v.cadd_score !== null && v.cadd_score !== undefined) {
      scores.push(`CADD: ${v.cadd_score.toFixed(1)}`);
    }
    if (v.gnomad_af !== null && v.gnomad_af !== undefined && v.gnomad_af > 0) {
      scores.push(`gnomAD: ${(v.gnomad_af * 100).toExponential(2)}%`);
    } else if (v.gnomad_af === 0) {
      scores.push('Not in gnomAD');
    }
    if (scores.length > 0) {
      parts.push(scores.join(', ') + '.');
    }

    return parts.join(' ').substring(0, 160); // Google truncates at ~160 chars
  });

  // Build keywords including all variant notations
  const keywords = computed(() => {
    const v = variantRef.value;
    const kw = ['HNF1B', 'mutation', 'variant', 'MODY5', 'RCAD', 'renal cysts', 'diabetes'];

    if (v) {
      if (v.hgvs_c) kw.push(v.hgvs_c, `HNF1B ${v.hgvs_c}`);
      if (v.hgvs_p && v.hgvs_p !== 'p.?') kw.push(v.hgvs_p, `HNF1B ${v.hgvs_p}`);
      if (v.rsid) kw.push(v.rsid);
      if (v.type) kw.push(v.type);
      if (v.consequence) kw.push(v.consequence.replace(/_/g, ' '));
    }

    return kw.join(', ');
  });

  // Canonical URL
  const canonicalUrl = computed(() => {
    const v = variantRef.value;
    if (!v?.variant_id) return `${BASE_URL}/variants`;
    return `${BASE_URL}/variants/${encodeURIComponent(v.variant_id)}`;
  });

  // Apply meta tags
  useSeoMeta({
    title,
    description,
    keywords,
    ogTitle: title,
    ogDescription: description,
    ogUrl: canonicalUrl,
    ogType: 'article',
    ogImage: DEFAULT_IMAGE,
    ogSiteName: SITE_NAME,
    twitterCard: 'summary',
    twitterTitle: title,
    twitterDescription: description,
    robots: 'index, follow',
  });

  // Add canonical link
  useHead({
    link: [{ rel: 'canonical', href: canonicalUrl }],
  });

  return { title, description, keywords, canonicalUrl };
}

/**
 * Generate JSON-LD structured data for a variant page.
 * Uses Schema.org MedicalEntity types for rich search results.
 *
 * @param {Object} variant - Variant data
 * @returns {Object} JSON-LD structured data object
 */
export function useVariantStructuredData(variant) {
  const structuredData = computed(() => {
    const v = variant.value || variant;
    if (!v) return null;

    // Build alternate names for findability
    const alternateNames = [];
    if (v.hgvs_c) alternateNames.push(v.hgvs_c, `HNF1B:${v.hgvs_c}`);
    if (v.hgvs_p && v.hgvs_p !== 'p.?') alternateNames.push(v.hgvs_p);
    if (v.rsid) alternateNames.push(v.rsid);
    if (v.simple_id && v.simple_id !== v.hgvs_c) alternateNames.push(v.simple_id);

    return {
      '@context': 'https://schema.org',
      '@type': 'MedicalEntity',
      '@id': `${BASE_URL}/variants/${encodeURIComponent(v.variant_id || '')}#variant`,
      name: v.hgvs_c || v.variant_id || 'Unknown Variant',
      alternateName: alternateNames,
      description: `HNF1B gene variant ${v.hgvs_c || ''}${v.hgvs_p && v.hgvs_p !== 'p.?' ? ` (${v.hgvs_p})` : ''}. ${v.consequence?.replace(/_/g, ' ') || ''} variant associated with RCAD/MODY5.`,
      url: `${BASE_URL}/variants/${encodeURIComponent(v.variant_id || '')}`,
      code: [
        {
          '@type': 'MedicalCode',
          codeValue: v.hgvs_c || '',
          codingSystem: 'HGVS',
        },
        ...(v.rsid
          ? [
              {
                '@type': 'MedicalCode',
                codeValue: v.rsid,
                codingSystem: 'dbSNP',
                url: `https://www.ncbi.nlm.nih.gov/snp/${v.rsid}`,
              },
            ]
          : []),
      ],
      relevantSpecialty: [
        {
          '@type': 'MedicalSpecialty',
          name: 'Genetics',
        },
        {
          '@type': 'MedicalSpecialty',
          name: 'Nephrology',
        },
        {
          '@type': 'MedicalSpecialty',
          name: 'Endocrinology',
        },
      ],
      study: {
        '@type': 'MedicalStudy',
        studySubject: {
          '@type': 'MedicalCondition',
          name: 'Renal cysts and diabetes syndrome',
          alternateName: ['RCAD', 'MODY5', 'HNF1B-related disorder'],
          code: {
            '@type': 'MedicalCode',
            codeValue: 'MONDO:0010894',
            codingSystem: 'MONDO',
          },
        },
        healthCondition: {
          '@type': 'MedicalCondition',
          name: 'HNF1B-related disorder',
        },
      },
      isPartOf: {
        '@type': 'Dataset',
        '@id': `${BASE_URL}/#dataset`,
        name: 'HNF1B Database',
      },
    };
  });

  // Inject JSON-LD into page
  useHead({
    script: computed(() =>
      structuredData.value
        ? [
            {
              type: 'application/ld+json',
              innerHTML: JSON.stringify(structuredData.value),
            },
          ]
        : []
    ),
  });

  return { structuredData };
}

/**
 * Generate SEO meta tags for a phenopacket/individual page.
 *
 * @param {Object} phenopacket - Phenopacket data
 */
export function usePhenopacketSeo(phenopacket) {
  const ppRef = computed(() => phenopacket.value || phenopacket);

  const title = computed(() => {
    const pp = ppRef.value;
    if (!pp) return `Patient Case | ${SITE_NAME}`;
    const id = pp.subject?.id || pp.id || 'Unknown';
    return `Case ${id} - HNF1B Clinical Phenotype | ${SITE_NAME}`;
  });

  const description = computed(() => {
    const pp = ppRef.value;
    if (!pp) return 'HNF1B patient case with clinical phenotype and genetic variant data.';

    const parts = ['HNF1B clinical case'];

    // Sex
    if (pp.subject?.sex) {
      const sexMap = { MALE: 'male', FEMALE: 'female' };
      parts.push(`(${sexMap[pp.subject.sex] || pp.subject.sex.toLowerCase()})`);
    }

    // Phenotype count
    const featureCount = pp.phenotypicFeatures?.length || 0;
    if (featureCount > 0) {
      parts.push(`with ${featureCount} clinical features`);
    }

    // Variant info
    const variants = pp.interpretations?.[0]?.diagnosis?.genomicInterpretations || [];
    if (variants.length > 0) {
      const variantNotation =
        variants[0]?.variantInterpretation?.variationDescriptor?.expressions?.[0]?.value;
      if (variantNotation) {
        parts.push(`including ${variantNotation}`);
      }
    }

    // Disease
    const diseases = pp.diseases || [];
    if (diseases.length > 0) {
      parts.push('- RCAD/MODY5');
    }

    return parts.join(' ').substring(0, 160);
  });

  const canonicalUrl = computed(() => {
    const pp = ppRef.value;
    if (!pp?.id) return `${BASE_URL}/phenopackets`;
    return `${BASE_URL}/phenopackets/${encodeURIComponent(pp.id)}`;
  });

  useSeoMeta({
    title,
    description,
    ogTitle: title,
    ogDescription: description,
    ogUrl: canonicalUrl,
    ogType: 'article',
    ogImage: DEFAULT_IMAGE,
    ogSiteName: SITE_NAME,
    twitterCard: 'summary',
    robots: 'index, follow',
  });

  useHead({
    link: [{ rel: 'canonical', href: canonicalUrl }],
  });

  return { title, description, canonicalUrl };
}

/**
 * Generate SEO meta tags for a publication page.
 *
 * @param {Object} publication - Publication data with title, authors, year, pmid
 */
export function usePublicationSeo(publication) {
  const pubRef = computed(() => publication.value || publication);

  const title = computed(() => {
    const pub = pubRef.value;
    if (!pub) return `Publication | ${SITE_NAME}`;

    // Truncate long titles
    const pubTitle = pub.title?.length > 60 ? pub.title.substring(0, 57) + '...' : pub.title;
    return `${pubTitle || 'Publication'} | ${SITE_NAME}`;
  });

  const description = computed(() => {
    const pub = pubRef.value;
    if (!pub) return 'HNF1B-related publication from the literature.';

    const parts = [];

    if (pub.title) parts.push(pub.title);

    if (pub.authors) {
      const authorList = Array.isArray(pub.authors) ? pub.authors : [pub.authors];
      const firstAuthor = authorList[0];
      if (authorList.length > 1) {
        parts.push(`${firstAuthor} et al.`);
      } else if (firstAuthor) {
        parts.push(firstAuthor);
      }
    }

    if (pub.year) parts.push(`(${pub.year})`);
    if (pub.journal) parts.push(pub.journal);

    return parts.join(' ').substring(0, 160);
  });

  const canonicalUrl = computed(() => {
    const pub = pubRef.value;
    if (!pub?.pmid) return `${BASE_URL}/publications`;
    return `${BASE_URL}/publications/${pub.pmid}`;
  });

  useSeoMeta({
    title,
    description,
    ogTitle: title,
    ogDescription: description,
    ogUrl: canonicalUrl,
    ogType: 'article',
    ogImage: DEFAULT_IMAGE,
    ogSiteName: SITE_NAME,
    twitterCard: 'summary',
    robots: 'index, follow',
  });

  useHead({
    link: [{ rel: 'canonical', href: canonicalUrl }],
  });

  return { title, description, canonicalUrl };
}

/**
 * Generate ScholarlyArticle structured data for publications.
 *
 * @param {Object} publication - Publication data
 */
export function usePublicationStructuredData(publication) {
  const structuredData = computed(() => {
    const pub = publication.value || publication;
    if (!pub) return null;

    return {
      '@context': 'https://schema.org',
      '@type': 'ScholarlyArticle',
      '@id': `${BASE_URL}/publications/${pub.pmid || ''}#article`,
      headline: pub.title,
      author: (Array.isArray(pub.authors) ? pub.authors : [pub.authors])
        .filter(Boolean)
        .map((name) => ({
          '@type': 'Person',
          name,
        })),
      datePublished: pub.year ? `${pub.year}` : undefined,
      publisher: pub.journal
        ? {
            '@type': 'Organization',
            name: pub.journal,
          }
        : undefined,
      identifier: [
        pub.pmid
          ? {
              '@type': 'PropertyValue',
              propertyID: 'PMID',
              value: pub.pmid,
              url: `https://pubmed.ncbi.nlm.nih.gov/${pub.pmid}/`,
            }
          : null,
        pub.doi
          ? {
              '@type': 'PropertyValue',
              propertyID: 'DOI',
              value: pub.doi,
              url: `https://doi.org/${pub.doi}`,
            }
          : null,
      ].filter(Boolean),
      about: {
        '@type': 'Gene',
        name: 'HNF1B',
        alternateName: ['TCF2', 'MODY5'],
      },
      isPartOf: {
        '@type': 'Dataset',
        '@id': `${BASE_URL}/#dataset`,
        name: 'HNF1B Database',
      },
    };
  });

  useHead({
    script: computed(() =>
      structuredData.value
        ? [
            {
              type: 'application/ld+json',
              innerHTML: JSON.stringify(structuredData.value),
            },
          ]
        : []
    ),
  });

  return { structuredData };
}

/**
 * Generate FAQPage structured data from FAQ content JSON.
 *
 * @param {Object} faqContent - FAQ content loaded from JSON config
 * @returns {Object} FAQPage JSON-LD structured data
 */
export function useFaqStructuredData(faqContent) {
  const structuredData = computed(() => {
    const content = faqContent.value || faqContent;
    if (!content?.categories) return null;

    // Flatten all questions from all categories
    const allQuestions = [];
    for (const category of content.categories) {
      for (const q of category.questions || []) {
        // Extract text from answer content blocks
        let answerText = '';
        if (q.answer?.content) {
          for (const block of q.answer.content) {
            if (block.type === 'paragraph' && block.text) {
              // Strip markdown-like formatting
              answerText +=
                block.text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1') + ' ';
            } else if (block.type === 'list' && block.items) {
              answerText += block.items.join('. ') + ' ';
            }
          }
        }

        if (q.question && answerText.trim()) {
          allQuestions.push({
            '@type': 'Question',
            name: q.question,
            acceptedAnswer: {
              '@type': 'Answer',
              text: answerText.trim().substring(0, 500), // Limit answer length
            },
          });
        }
      }
    }

    if (allQuestions.length === 0) return null;

    return {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      '@id': `${BASE_URL}/faq#faq`,
      mainEntity: allQuestions,
    };
  });

  useHead({
    script: computed(() =>
      structuredData.value
        ? [
            {
              type: 'application/ld+json',
              innerHTML: JSON.stringify(structuredData.value),
            },
          ]
        : []
    ),
  });

  return { structuredData };
}

/**
 * Generate BreadcrumbList structured data.
 *
 * @param {Array} breadcrumbs - Array of {name, url} objects
 */
export function useBreadcrumbStructuredData(breadcrumbs) {
  const structuredData = computed(() => {
    const items = breadcrumbs.value || breadcrumbs;
    if (!items || items.length === 0) return null;

    return {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: items.map((item, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        name: item.name,
        item: item.url.startsWith('http') ? item.url : `${BASE_URL}${item.url}`,
      })),
    };
  });

  useHead({
    script: computed(() =>
      structuredData.value
        ? [
            {
              type: 'application/ld+json',
              innerHTML: JSON.stringify(structuredData.value),
            },
          ]
        : []
    ),
  });

  return { structuredData };
}

/**
 * Standard page SEO for static pages (Home, About, etc.)
 *
 * @param {Object} options - SEO options
 * @param {string} options.title - Page title
 * @param {string} options.description - Page description
 * @param {string} options.path - URL path (e.g., '/about')
 */
export function usePageSeo({ title, description, path }) {
  const fullTitle = `${title} | ${SITE_NAME}`;
  const canonicalUrl = `${BASE_URL}${path}`;

  useSeoMeta({
    title: fullTitle,
    description,
    ogTitle: fullTitle,
    ogDescription: description,
    ogUrl: canonicalUrl,
    ogType: 'website',
    ogImage: DEFAULT_IMAGE,
    ogSiteName: SITE_NAME,
    twitterCard: 'summary',
    robots: 'index, follow',
  });

  useHead({
    link: [{ rel: 'canonical', href: canonicalUrl }],
  });
}
