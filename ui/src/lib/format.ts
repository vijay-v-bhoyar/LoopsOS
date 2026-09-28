export function compactList(values: string[], limit = 3): string {
  if (!values.length) return "None recorded";
  if (values.length <= limit) return values.join(", ");
  return `${values.slice(0, limit).join(", ")} +${values.length - limit}`;
}
