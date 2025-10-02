// assets/js/mixins/colorAndSymbolsMixin.js
export default {
  data() {
    return {
      icons: {
        mdiPlusCircleOutline: 'mdi-plus-circle-outline',
        mdiMinusCircleOutline: 'mdi-minus-circle-outline',
        mdiHelpCircleOutline: 'mdi-help-circle-outline',
        mdiGenderFemale: 'mdi-gender-female',
        mdiGenderMale: 'mdi-gender-male',
        mdiCheckCircleOutline: 'mdi-check-circle-outline',
        mdiAccount: 'mdi-account',
        mdiAccountCowboyHat: 'mdi-account-cowboy-hat',
        mdiAccountSchool: 'mdi-account-school',
        mdiDna: 'mdi-dna',
        mdiNewspaperVariant: 'mdi-newspaper-variant',
        mdiBookOpenBlankVariant: 'mdi-book-open-blank-variant',
        mdiRefresh: 'mdi-refresh',
        mdiLogout: 'mdi-logout',
        mdiDownload: 'mdi-download',
        mdiDotsVertical: 'mdi-dots-vertical',
        mdiGithub: 'mdi-github',
        mdiCopyright: 'mdi-copyright',
        mdiApi: 'mdi-api',
        mdiMagnify: 'mdi-magnify',
        mdiChevronDown: 'mdi-chevron-down',
        mdiDatabase: 'mdi-database',
        mdiEmail: 'mdi-email',
        mdiLock: 'mdi-lock',
        mdiEye: 'mdi-eye',
        mdiEyeOff: 'mdi-eye-off',
        mdiFormTextbox: 'mdi-form-textbox',
      },
      type_color: {
        individual: 'lime lighten-2',
        variant: 'pink lighten-4',
        report: 'deep-orange lighten-2',
        publication: 'cyan accent-2',
      },
      cohort_color: {
        born: 'success',
        fetus: 'primary',
      },
      reported_phenotype_color: {
        yes: 'teal lighten-1',
        no: 'light-blue',
        'not reported': 'white',
      },
      variant_class_color: {
        copy_number_gain: '#3466C8',
        copy_number_loss: '#DB3B1F',
        SNV: '#17962A',
        insertion: '#FE9A2B',
        deletion: '#FE9A2B',
        indel: '#FE9A2B',
      },
      impact_color: {
        HIGH: '#FE5F55',
        MODERATE: '#90CAF9',
        LOW: '#C7EFCF',
        MODIFIER: '#FFFFFF',
      },
      classification_color: {
        Pathogenic: 'deep-orange darken-3',
        'Likely Pathogenic': 'deep-orange darken-1',
        'Uncertain Significance': 'orange lighten-1',
        'Likely Benign': 'green lighten-2',
        Benign: 'green darken-4',
      },
      criteria_color: {
        P: {
          VeryStrong: 'deep-orange darken-3',
          Strong: 'deep-orange darken-1',
          Moderate: 'orange darken-2',
          Supporting: 'orange lighten-1',
        },
        B: {
          VeryStrong: 'green darken-4',
          Strong: 'green darken-2',
          Moderate: 'green lighten-2',
          Supporting: 'green lighten-4',
        },
      },
      cohort_style: {
        born: 'success',
        fetus: 'primary',
      },
      type_symbol: {
        individual: 'mdi-account',
        variant: 'mdi-dna',
        report: 'mdi-newspaper-variant',
        publication: 'mdi-book-open-blank-variant',
      },
      reported_phenotype_symbol: {
        yes: 'mdi-plus-circle-outline',
        no: 'mdi-minus-circle-outline',
        'not reported': 'mdi-help-circle-outline',
      },
      sex_symbol: {
        female: 'mdi-gender-female',
        male: 'mdi-gender-male',
        unspecified: 'mdi-help-circle-outline',
      },
      logical_symbol: {
        1: 'mdi-check-circle-outline',
        0: 'mdi-minus-circle-outline',
      },
      user_symbol: {
        Administrator: 'mdi-account-cowboy-hat',
        Reviewer: 'mdi-account-school',
      },
    };
  },
};
