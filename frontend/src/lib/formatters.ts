/**
 * Deterministic financial presentation helpers.
 * Note: Does not mutate or compute math, strictly formats string values.
 */

export function formatCurrency(amount: string | number, currency = 'INR'): string {
  if (amount === undefined || amount === null) return '-';
  const str = String(amount);
  const parts = str.split('.');
  const intPart = parts[0];
  const decPart = parts[1] !== undefined ? `.${parts[1]}` : '';

  // Use Intl.NumberFormat on integer part only to avoid float truncation on big decimals
  let formattedInt = intPart;
  try {
    const bigIntVal = BigInt(intPart);
    formattedInt = new Intl.NumberFormat('en-IN').format(bigIntVal);
  } catch {
    formattedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  return `${currency} ${formattedInt}${decPart}`;
}

export function formatMetric(val: string | number | undefined | null, maxDecimals = 2): string {
  if (val === undefined || val === null || val === '') return '0.00';
  const str = String(val);
  const parts = str.split('.');
  if (parts.length === 1) return parts[0];
  const dec = parts[1].substring(0, maxDecimals);
  return `${parts[0]}.${dec}`;
}

export function formatTimestamp(isoString: string): string {
  if (!isoString) return '-';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return date.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  } catch {
    return isoString;
  }
}

export function formatShortHash(hash: string, chars = 8): string {
  if (!hash || hash.length <= chars * 2) return hash;
  return `${hash.substring(0, chars)}...${hash.substring(hash.length - chars)}`;
}
