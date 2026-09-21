import en from "../../messages/en.json";
import hi from "../../messages/hi.json";

/**
 * Locale parity guard: en.json is the source of truth for message keys
 * (see global.ts / docs/i18n.md). A key missing from any locale throws
 * `IntlError` at render time — fail the suite instead.
 */

type Messages = Record<string, unknown>;

/** Flatten nested message objects to dot-separated leaf paths. */
function flattenKeys(obj: Messages, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value !== null && typeof value === "object" && !Array.isArray(value)
      ? flattenKeys(value as Messages, path)
      : [path];
  });
}

function leafMap(obj: Messages, prefix = ""): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(out, leafMap(value as Messages, path));
    } else {
      out[path] = value;
    }
  }
  return out;
}

/** ICU argument names ({count}) and rich-text tag names (<link>) in a message. */
function placeholdersOf(message: string): string[] {
  const found: string[] = [];
  for (const re of [/\{(\w+)[,}]/g, /<(\w+)>/g]) {
    let m: RegExpExecArray | null;
    while ((m = re.exec(message)) !== null) found.push(m[1]);
  }
  return found.sort();
}

describe("messages parity (en ↔ hi)", () => {
  const enKeys = flattenKeys(en);
  const hiKeys = flattenKeys(hi);

  it("has identical key sets across locales", () => {
    expect(hiKeys.sort()).toEqual(enKeys.sort());
  });

  it("has no empty message values", () => {
    const empty: string[] = [];
    for (const [locale, messages] of Object.entries({ en, hi })) {
      for (const [key, value] of Object.entries(leafMap(messages))) {
        if (typeof value !== "string" || value.trim().length === 0) {
          empty.push(`${locale}:${key}`);
        }
      }
    }
    expect(empty).toEqual([]);
  });

  it("uses the same ICU placeholders / rich tags per key", () => {
    const enLeaves = leafMap(en);
    const hiLeaves = leafMap(hi);
    const mismatched = enKeys.filter(
      (key) =>
        JSON.stringify(placeholdersOf(hiLeaves[key] as string)) !==
        JSON.stringify(placeholdersOf(enLeaves[key] as string))
    );
    expect(mismatched).toEqual([]);
  });
});
