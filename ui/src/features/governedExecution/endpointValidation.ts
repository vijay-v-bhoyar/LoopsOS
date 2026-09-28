export function requireConnectorUrl(value: string, label: string): string {
  const candidate = value.trim();
  if (!candidate) throw new Error(`${label} is required.`);
  if (candidate.includes("\\")) throw new Error(`${label} cannot contain backslashes.`);
  if (candidate.includes("?") || candidate.includes("#")) throw new Error(`${label} cannot contain query strings or fragments.`);

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error(`${label} must be a valid URL.`);
  }

  if (parsed.username || parsed.password) throw new Error(`${label} cannot contain embedded credentials.`);
  const hostname = parsed.hostname.toLowerCase();
  const localDevelopment = parsed.protocol === "http:" && (hostname === "localhost" || hostname === "127.0.0.1");
  if (parsed.protocol !== "https:" && !localDevelopment) {
    throw new Error(`${label} must use HTTPS except for localhost development.`);
  }
  return parsed.toString();
}
