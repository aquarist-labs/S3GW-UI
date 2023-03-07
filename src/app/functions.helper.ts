import * as _ from 'lodash';

/**
 * Convert a binary value into bytes.
 *
 * @param value The value to convert, e.g. '1024', '512MiB' or '2 G'.
 * @returns Returns the value in bytes or NULL in case of an error.
 */
export const toBytes = (value: number | string): number | null => {
  const base = 1024;
  const units = ['b', 'k', 'm', 'g', 't', 'p', 'e', 'z', 'y'];
  const m = RegExp('^(\\d+(.\\d+)?) ?([' + units.join('') + ']?(b|ib|B/s)?)?$', 'i').exec(
    String(value)
  );
  if (_.isNull(m)) {
    return null;
  }
  let bytes = parseFloat(m[1]);
  if (_.isString(m[3])) {
    bytes = bytes * Math.pow(base, units.indexOf(m[3].toLowerCase()[0]));
  }
  return Math.round(bytes);
};

/**
 * Convert a number of bytes into the highest possible binary unit.
 *
 * @param value The value to convert.
 * @returns Returns The converted value, e.g. '4 MiB'.
 */
export const bytesToSize = (value: undefined | null | number | string): string => {
  if (_.isUndefined(value) || _.isNull(value) || [0, '0', ''].includes(value)) {
    return '0 B';
  }
  const bytes = _.toNumber(value);
  const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
  const factor = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(factor));
  const rawVal = bytes / Math.pow(factor, i);
  const rounded = Math.round((rawVal + Number.EPSILON) * 100) / 100;
  return rounded + ' ' + sizes[i];
};

/**
 * Format a string.
 *
 * Use this function if you want to format translated text. Using the
 * mustache style for that seems to be the better approach than using
 * the ES string interpolate style.
 *
 * Example:
 * format('Hello {{ username }}', {username: 'foo'})
 *
 * @param str The template string.
 * @param options The options object.
 */
export const format = (str: string, options: Record<any, any>): string => {
  _.templateSettings.interpolate = /{{([\s\S]+?)}}/g;
  const compiled = _.template(str);
  return compiled(options);
};

/**
 * Try to extract the error code from an error object. This might
 * be provided by the RGW Admin Ops or the S3 API.
 */
export const extractErrorCode = (err: Record<string, any>): string =>
  err['code'] ?? (_.isString(err['error']) ? err['error'] : err['statusText']);

/**
 * Decorator that creates a throttled function that only invokes func at
 * most once per every wait milliseconds.
 *
 * @param wait The number of milliseconds to throttle invocations to.
 */
// eslint-disable-next-line @typescript-eslint/naming-convention,prefer-arrow/prefer-arrow-functions
export function Throttle(wait: number) {
  return (target: any, propertyKey: string, descriptor: PropertyDescriptor) => {
    const originalFn = descriptor.value;
    descriptor.value = _.throttle(originalFn, wait);
    return descriptor;
  };
}

/**
 * Compare the specified values.
 *
 * @param value The value to compare.
 * @param other The other value to compare.
 * @return Returns `true` if the values are equivalent, else `false`.
 *   Note, `true` will be returned if one of the values is `undefined`.
 */
export const isEqualOrUndefined = (value: any, other: any) => {
  if (_.isUndefined(value) || _.isUndefined(other)) {
    return true;
  }
  return _.isEqual(value, other);
};
