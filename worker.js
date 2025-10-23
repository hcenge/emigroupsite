export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Get the static asset from the KV namespace or R2 bucket
    let response = await env.ASSETS.fetch(request);

    // If not found, try appending /index.html for clean URLs
    if (response.status === 404) {
      const indexUrl = new URL(url.pathname + '/index.html', url.origin);
      const indexRequest = new Request(indexUrl, request);
      response = await env.ASSETS.fetch(indexRequest);
    }

    // Still not found? Try /index.html at the path
    if (response.status === 404 && !url.pathname.endsWith('/')) {
      const cleanUrl = new URL(url.pathname + '/index.html', url.origin);
      const cleanRequest = new Request(cleanUrl, request);
      response = await env.ASSETS.fetch(cleanRequest);
    }

    return response;
  },
};
