// Cloudflare Worker: GitHub OAuth proxy for Decap CMS
// Handles the OAuth code→token exchange that requires a client secret.

const GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize";
const GITHUB_TOKEN = "https://github.com/login/oauth/access_token";

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "*";

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(origin) });
    }

    // Step 1: Redirect user to GitHub login
    if (url.pathname === "/auth") {
      const params = new URLSearchParams({
        client_id: env.GITHUB_CLIENT_ID,
        redirect_uri: `${url.origin}/callback`,
        scope: "repo,user",
      });
      return Response.redirect(`${GITHUB_AUTHORIZE}?${params}`, 302);
    }

    // Step 2: GitHub redirects back here with a code
    if (url.pathname === "/callback") {
      const code = url.searchParams.get("code");
      if (!code) {
        return new Response("Missing code parameter", { status: 400 });
      }

      // Exchange code for access token
      const tokenRes = await fetch(GITHUB_TOKEN, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code,
        }),
      });

      const data = await tokenRes.json();

      if (data.error) {
        return new Response(`OAuth error: ${data.error_description}`, {
          status: 400,
        });
      }

      // Send token back to Decap CMS via postMessage
      const html = `<!doctype html>
<html><body><script>
(function() {
  function sendMsg(msg) {
    var o = msg.origin || "https://github.com";
    if (window.opener) {
      window.opener.postMessage(
        'authorization:github:success:${JSON.stringify({ token: data.access_token, provider: "github" })}',
        o
      );
    }
  }
  sendMsg({ origin: "*" });
  window.addEventListener("message", sendMsg, false);
})();
</script></body></html>`;

      return new Response(html, {
        headers: { "Content-Type": "text/html" },
      });
    }

    return new Response("Not found", { status: 404 });
  },
};
