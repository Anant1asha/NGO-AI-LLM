import http from 'node:http';

function compilePath(pattern) {
  const keys = [];
  const regexStr = '^' + pattern.replace(/:([A-Za-z0-9_]+)/g, (_, k) => {
    keys.push(k);
    return '([^/]+)';
  }) + '$';
  return { regex: new RegExp(regexStr), keys };
}

export default function Fastify() {
  const routes = [];
  let server = null;

  const app = {
    register() { return app; },
    get(pattern, handler) {
      routes.push({ method: 'GET', ...compilePath(pattern), handler });
      return app;
    },
    post(pattern, handler) {
      routes.push({ method: 'POST', ...compilePath(pattern), handler });
      return app;
    },
    async listen({ port = 0, host = '127.0.0.1' } = {}) {
      server = http.createServer(async (req, res) => {
        const url = new URL(req.url, `http://${host}`);
        const method = req.method.toUpperCase();
        const chunks = [];
        for await (const c of req) chunks.push(c);
        const rawBody = Buffer.concat(chunks).toString('utf8');
        let body = {};
        if (rawBody) {
          try { body = JSON.parse(rawBody); } catch { body = {}; }
        }

        let matched = null;
        let params = {};
        for (const r of routes) {
          if (r.method !== method) continue;
          const m = url.pathname.match(r.regex);
          if (m) {
            matched = r;
            r.keys.forEach((k, idx) => { params[k] = decodeURIComponent(m[idx + 1]); });
            break;
          }
        }

        if (!matched) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'NOT_FOUND' }));
          return;
        }

        let statusCode = 200;
        let sent = false;
        const reply = {
          code(c) { statusCode = c; return reply; },
          send(payload) {
            sent = true;
            res.writeHead(statusCode, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(payload));
            return reply;
          }
        };

        try {
          const result = await matched.handler({ params, body, query: Object.fromEntries(url.searchParams) }, reply);
          if (!sent && result !== undefined) {
            res.writeHead(statusCode, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(result));
          }
        } catch (err) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: err.message }));
        }
      });

      await new Promise((resolve) => server.listen(port, host, resolve));
      const addr = server.address();
      return `http://${host}:${addr.port}`;
    },
    async close() {
      if (server) {
        await new Promise((resolve) => server.close(resolve));
      }
    }
  };
  return app;
}
