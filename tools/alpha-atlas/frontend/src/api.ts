// Same-origin thin client (vite dev proxies /api to the backend on :8803).

export async function getJSON<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`${response.status} ${url}: ${body.slice(0, 200)}`)
  }
  return (await response.json()) as T
}
