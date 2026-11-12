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
  expect(r.status).toBe(201); // 201 Created
  expect(r.body).toEqual({ saved: "note-1.txt" });
  expect(saved).toEqual(["hello"]);
});

test("notes returns 502 with a generic body when storage fails", async () => {
  // The real error is logged, so silence it here and check it was logged.
  const logged = jest.spyOn(console, "error").mockImplementation(() => {});
  const app = makeApp({
    saveNote: async () => {
      throw new Error("secret bucket ocid1.bucket.oc1..xyz denied");
    },
  });
  const r = await request(app).post("/notes").send({ text: "hello" });
  expect(r.status).toBe(502);
  expect(r.body).toEqual({ error: "could not save note" });
  // The internal error text must never reach the caller.
  expect(JSON.stringify(r.body)).not.toContain("secret");
  expect(JSON.stringify(r.body)).not.toContain("ocid1");
  // The real error is logged for operators.
  expect(logged).toHaveBeenCalled();
  expect(String(logged.mock.calls[0])).toContain("secret bucket");
  logged.mockRestore();
});

test("notes returns 422 when text is missing", async () => {
  const r = await request(makeApp()).post("/notes").send({});
  expect(r.status).toBe(422);
});
