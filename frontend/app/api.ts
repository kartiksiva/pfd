const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "/api").replace(/\/$/, "");

export { apiBase };

export function joinApiPath(input: string): string {
  const normalizedInput = input.startsWith("/api/") ? input.slice(4) : input;
  const path = normalizedInput.startsWith("/") ? normalizedInput : `/${normalizedInput}`;
  return `${apiBase}${path}`;
}

export async function apiFetch(
  input: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const { timeoutMs = 30_000, ...fetchInit } = init ?? {};
  const controller = new AbortController();
  const timerId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(joinApiPath(input), {
      ...fetchInit,
      credentials: "include",
      signal: fetchInit.signal ?? controller.signal,
    });
  } finally {
    clearTimeout(timerId);
  }
}
