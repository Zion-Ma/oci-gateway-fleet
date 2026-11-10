import os from "os";
import request from "supertest";
import { createApp, Deps } from "../src/app";

function makeApp(overrides: Partial<Deps> = {}) {
  return createApp({
    version: "v1",
    fetchPublicSite: async () => {},
    saveNote: async () => "note-1.txt",
    ...overrides,
  });
}

test("health reports ok and version", async () => {
  const r = await request(makeApp({ version: "v2" })).get("/health");
  expect(r.status).toBe(200);
  expect(r.body).toEqual({ status: "ok", version: "v2" });
});

test("health default version is v1", async () => {
  const r = await request(makeApp()).get("/health");
  expect(r.body.version).toBe("v1");
});

test("whoami returns hostname", async () => {
  const r = await request(makeApp()).get("/whoami");
  expect(r.status).toBe(200);
  expect(r.body).toEqual({ hostname: os.hostname() });
});

test("egress ok when site reachable", async () => {
  const r = await request(makeApp()).get("/egress");
  expect(r.status).toBe(200);
  expect(r.body).toEqual({ egress: "ok" });
});

test("egress fail when site unreachable", async () => {
  const app = makeApp({
    fetchPublicSite: async () => {
      throw new Error("network unreachable");
    },
  });
  const r = await request(app).get("/egress");
  expect(r.status).toBe(200);
  expect(r.body.egress).toBe("fail");
});

test("notes saves via storage function", async () => {
  const saved: string[] = [];
  const app = makeApp({
    saveNote: async (t) => {
      saved.push(t);
      return "note-1.txt";
    },
  });
  const r = await request(app).post("/notes").send({ text: "hello" });
  expect(r.status).toBe(200);
  expect(r.body).toEqual({ saved: "note-1.txt" });
  expect(saved).toEqual(["hello"]);
});

test("notes returns 502 when storage fails", async () => {
  const app = makeApp({
    saveNote: async () => {
      throw new Error("service gateway down");
    },
  });
  const r = await request(app).post("/notes").send({ text: "hello" });
  expect(r.status).toBe(502);
});

test("notes returns 422 when text is missing", async () => {
  const r = await request(makeApp()).post("/notes").send({});
  expect(r.status).toBe(422);
});
