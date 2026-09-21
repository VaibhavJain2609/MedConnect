/**
 * Jest mock for `next-intl` (mapped via moduleNameMapper in jest.config.js).
 *
 * next-intl/use-intl ship ESM that next/jest's hardcoded transformIgnorePatterns
 * refuse to transform, so components using useTranslations/useFormatter can't be
 * imported under jest as-is. This mock resolves real messages from
 * messages/en.json so rendered output (and test assertions) match production
 * English, with a minimal ICU subset: {arg} interpolation, {n, plural, ...},
 * and rich-tag stripping for t.rich.
 */

import React from "react";
import enMessages from "../../messages/en.json";

type Messages = Record<string, unknown>;

function resolveMessage(namespace: string | undefined, key: string): string {
  const path = namespace ? `${namespace}.${key}` : key;
  let node: unknown = enMessages;
  for (const part of path.split(".")) {
    node = (node as Messages)?.[part];
  }
  return typeof node === "string" ? node : path;
}

/** Minimal ICU: {name} interpolation + {count, plural, one {…} other {…}}. */
function interpolate(message: string, values?: Record<string, unknown>): string {
  if (!values) return message;
  const plural = message.replace(
    /\{(\w+),\s*plural,\s*one\s*\{([^{}]*)\}\s*other\s*\{([^{}]*)\}\s*\}/g,
    (_m, name: string, one: string, other: string) => {
      const v = values[name];
      return (v === 1 ? one : other).replace(/#/g, String(v));
    }
  );
  return plural.replace(/\{(\w+)\}/g, (_m, name: string) =>
    values[name] !== undefined ? String(values[name]) : `{${name}}`
  );
}

/** Strip <tag>…</tag> rich markers — test output keeps the inner text. */
function stripTags(message: string): string {
  return message.replace(/<\/?\w+>/g, "");
}

export function useTranslations(namespace?: string) {
  const t = (key: string, values?: Record<string, unknown>) =>
    interpolate(resolveMessage(namespace, key), values);
  t.rich = (key: string, values?: Record<string, unknown>) =>
    stripTags(interpolate(resolveMessage(namespace, key), values));
  t.markup = t.rich;
  t.raw = (key: string) => {
    const path = namespace ? `${namespace}.${key}` : key;
    let node: unknown = enMessages;
    for (const part of path.split(".")) node = (node as Messages)?.[part];
    return node;
  };
  t.has = () => true;
  return t;
}

export function useFormatter() {
  return {
    dateTime: (value: Date | number, options?: Intl.DateTimeFormatOptions) =>
      new Intl.DateTimeFormat("en-IN", options).format(value),
    number: (value: number, options?: Intl.NumberFormatOptions) =>
      new Intl.NumberFormat("en-IN", options).format(value),
    relativeTime: (value: Date | number) =>
      new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
        Math.round(((typeof value === "number" ? value : value.getTime()) - Date.now()) / 86400000),
        "day"
      ),
    list: (value: string[]) => value.join(", "),
    now: () => new Date(),
  };
}

export function useLocale() {
  return "en";
}

export function useMessages() {
  return enMessages;
}

export function useNow() {
  return new Date();
}

export function useTimeZone() {
  return "Asia/Kolkata";
}

export function NextIntlClientProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export const IntlProvider = NextIntlClientProvider;
