const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "/api").replace(/\/$/, "");

export { apiBase };

export function joinApiPath(input: string): string {
  const normalizedInput = input.startsWith("/api/") ? input.slice(4) : input;
  const path = normalizedInput.startsWith("/") ? normalizedInput : `/${normalizedInput}`;
  return `${apiBase}${path}`;
}

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  return fetch(joinApiPath(input), {
    ...init,
    credentials: "include",
  });
}
