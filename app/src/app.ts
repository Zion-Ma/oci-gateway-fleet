import express from "express";
import os from "os";

// Everything the app needs from outside itself. server.ts passes in the real
// versions; tests pass in fakes, so they run offline.
export interface Deps {
  version: string; // reported by /health, so a rollout (v1 -> v2) is visible
  fetchPublicSite: () => Promise<void>; // throws if the internet is unreachable
  saveNote: (text: string) => Promise<string>; // returns the saved file name
}

// Builds the web app but doesn't start it (server.ts does that), so tests can
// call it directly without opening a port.
export function createApp(deps: Deps) {
  const app = express();
  app.use(express.json()); // parse JSON request bodies into req.body

  // The load balancer calls this to decide if the server is healthy.
  app.get("/health", (_req, res) => {
    res.json({ status: "ok", version: deps.version });
  });

  // Shows which server answered, to confirm load balancing works.
  app.get("/whoami", (_req, res) => {
    res.json({ hostname: os.hostname() });
  });

  // Tries to reach a public site. Proves the NAT Gateway path works.
  // Always answers 200; the body says ok or fail.
  app.get("/egress", async (_req, res) => {
    try {
      await deps.fetchPublicSite();
      res.json({ egress: "ok" });
    } catch (e) {
      res.json({ egress: "fail", error: String(e) });
    }
  });

  // Saves a note to Object Storage. Proves the Service Gateway path works.
  app.post("/notes", async (req, res) => {
    const text = req.body?.text;
    if (typeof text !== "string") {
      res.status(422).json({ detail: "text (string) is required" }); // bad request
      return;
    }
    try {
      res.json({ saved: await deps.saveNote(text) });
    } catch (e) {
      res.status(502).json({ detail: String(e) }); // storage failed, not the caller's fault
    }
  });

  return app;
}
