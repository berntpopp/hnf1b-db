/**
 * Bounded-precision ESM replacement for `sprintf-js` (used transitively by `ngl`).
 *
 * Remediates GHSA-hp3w-g68c-fv3c / CVE-2026-97058 by clamping precision
 * specifiers passed to `toExponential`, `toFixed`, and `toPrecision` within
 * ECMAScript bounds ([0, 100] for %e/%f, [1, 100] for %g) so unbounded
 * precision strings cannot trigger uncaught RangeError exceptions.
 */

const RE = {
  notString: /[^s]/,
  notBool: /[^t]/,
  notType: /[^T]/,
  notPrimitive: /[^v]/,
  number: /[diefg]/,
  numericArg: /[bcdiefguxX]/,
  json: /[j]/,
  text: /^[^%]+/,
  modulo: /^%{2}/,
  placeholder:
    /^%(?:([1-9]\d*)\$|\(([^)]+)\))?(\+)?(0|'[^$])?(-)?(\d+)?(?:\.(\d+))?([b-gijostTuvxX])/,
  key: /^([a-z_][a-z_\d]*)/i,
  keyAccess: /^\.([a-z_][a-z_\d]*)/i,
  indexAccess: /^\[(\d+)\]/,
  sign: /^[+-]/,
};

const MAX_PRECISION = 100;
const parseCache = Object.create(null);

function clampPrecision(rawPrecision, min = 0, max = MAX_PRECISION) {
  const parsed = Number.parseInt(rawPrecision, 10);
  if (Number.isNaN(parsed)) {
    return min;
  }
  return Math.min(Math.max(parsed, min), max);
}

export function sprintf(key, ...rest) {
  return sprintfFormat(sprintfParse(key), [key, ...rest]);
}

export function vsprintf(fmt, argv) {
  return sprintf(fmt, ...(argv || []));
}

function sprintfFormat(parseTree, argv) {
  let cursor = 1;
  const treeLength = parseTree.length;
  let output = '';

  for (let i = 0; i < treeLength; i++) {
    const node = parseTree[i];
    if (typeof node === 'string') {
      output += node;
      continue;
    }
    if (typeof node !== 'object' || node === null) {
      continue;
    }

    const ph = node;
    let arg;
    if (ph.keys) {
      arg = argv[cursor];
      for (let k = 0; k < ph.keys.length; k++) {
        if (arg == null) {
          throw new Error(
            sprintf(
              '[sprintf] Cannot access property "%s" of undefined value "%s"',
              ph.keys[k],
              ph.keys[k - 1]
            )
          );
        }
        arg = arg[ph.keys[k]];
      }
    } else if (ph.paramNo) {
      arg = argv[ph.paramNo];
    } else {
      arg = argv[cursor++];
    }

    if (RE.notType.test(ph.type) && RE.notPrimitive.test(ph.type) && typeof arg === 'function') {
      arg = arg();
    }

    if (RE.numericArg.test(ph.type) && typeof arg !== 'number' && Number.isNaN(Number(arg))) {
      throw new TypeError(sprintf('[sprintf] expecting number but found %T', arg));
    }

    let isPositive = false;
    if (RE.number.test(ph.type)) {
      isPositive = arg >= 0;
    }

    switch (ph.type) {
      case 'b':
        arg = Number.parseInt(arg, 10).toString(2);
        break;
      case 'c':
        arg = String.fromCharCode(Number.parseInt(arg, 10));
        break;
      case 'd':
      case 'i':
        arg = Number.parseInt(arg, 10);
        break;
      case 'j':
        arg = JSON.stringify(arg, null, ph.width ? Number.parseInt(ph.width, 10) : 0);
        break;
      case 'e':
        arg = ph.precision
          ? Number.parseFloat(arg).toExponential(clampPrecision(ph.precision, 0, MAX_PRECISION))
          : Number.parseFloat(arg).toExponential();
        break;
      case 'f':
        arg = ph.precision
          ? Number.parseFloat(arg).toFixed(clampPrecision(ph.precision, 0, MAX_PRECISION))
          : Number.parseFloat(arg);
        break;
      case 'g':
        arg = ph.precision
          ? String(
              Number(
                Number.parseFloat(arg).toPrecision(clampPrecision(ph.precision, 1, MAX_PRECISION))
              )
            )
          : Number.parseFloat(arg);
        break;
      case 'o':
        arg = (Number.parseInt(arg, 10) >>> 0).toString(8);
        break;
      case 's':
        arg = String(arg);
        arg = ph.precision ? arg.substring(0, ph.precision) : arg;
        break;
      case 't':
        arg = String(Boolean(arg));
        arg = ph.precision ? arg.substring(0, ph.precision) : arg;
        break;
      case 'T':
        arg = Object.prototype.toString.call(arg).slice(8, -1).toLowerCase();
        arg = ph.precision ? arg.substring(0, ph.precision) : arg;
        break;
      case 'u':
        arg = Number.parseInt(arg, 10) >>> 0;
        break;
      case 'v':
        arg = arg.valueOf();
        arg = ph.precision ? arg.substring(0, ph.precision) : arg;
        break;
      case 'x':
        arg = (Number.parseInt(arg, 10) >>> 0).toString(16);
        break;
      case 'X':
        arg = (Number.parseInt(arg, 10) >>> 0).toString(16).toUpperCase();
        break;
    }

    if (RE.json.test(ph.type)) {
      output += arg;
    } else {
      let sign = '';
      if (RE.number.test(ph.type) && (!isPositive || ph.sign)) {
        sign = isPositive ? '+' : '-';
        arg = arg.toString().replace(RE.sign, '');
      }
      const padCharacter = ph.padChar ? (ph.padChar === '0' ? '0' : ph.padChar.charAt(1)) : ' ';
      const padLength = (ph.width || 0) - (sign + arg).length;
      const pad = ph.width && padLength > 0 ? padCharacter.repeat(padLength) : '';
      output += ph.align
        ? sign + arg + pad
        : padCharacter === '0'
          ? sign + pad + arg
          : pad + sign + arg;
    }
  }

  return output;
}

function sprintfParse(fmt) {
  if (parseCache[fmt]) {
    return parseCache[fmt];
  }

  let rest = fmt;
  const parseTree = [];
  let argNames = 0;

  while (rest) {
    let match = RE.text.exec(rest);
    if (match !== null) {
      parseTree.push(match[0]);
    } else if ((match = RE.modulo.exec(rest)) !== null) {
      parseTree.push('%');
    } else if ((match = RE.placeholder.exec(rest)) !== null) {
      let keys = match[2];
      if (keys) {
        argNames |= 1;
        const fieldList = [];
        let replacementField = keys;
        let fieldMatch = RE.key.exec(replacementField);
        if (fieldMatch !== null) {
          fieldList.push(fieldMatch[1]);
          while ((replacementField = replacementField.substring(fieldMatch[0].length)) !== '') {
            if ((fieldMatch = RE.keyAccess.exec(replacementField)) !== null) {
              fieldList.push(fieldMatch[1]);
            } else if ((fieldMatch = RE.indexAccess.exec(replacementField)) !== null) {
              fieldList.push(fieldMatch[1]);
            } else {
              throw new SyntaxError('[sprintf] failed to parse named argument key');
            }
          }
        } else {
          throw new SyntaxError('[sprintf] failed to parse named argument key');
        }
        keys = fieldList;
      } else {
        argNames |= 2;
      }
      if (argNames === 3) {
        throw new Error(
          '[sprintf] mixing positional and named placeholders is not (yet) supported'
        );
      }

      parseTree.push({
        placeholder: match[0],
        paramNo: match[1],
        keys,
        sign: match[3],
        padChar: match[4],
        align: match[5],
        width: match[6],
        precision: match[7],
        type: match[8],
      });
    } else {
      throw new SyntaxError('[sprintf] unexpected placeholder');
    }
    rest = rest.substring(match[0].length);
  }

  parseCache[fmt] = parseTree;
  return parseTree;
}

export default { sprintf, vsprintf };
