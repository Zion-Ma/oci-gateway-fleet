import { randomBytes } from "crypto";
import { createApp, Deps } from "./app";

// Settings come from environment variables, so the same code runs everywhere.
const VERSION = process.env.APP_VERSION ?? "v1"; // set to v2 for the rollout
const BUCKET = process.env.NOTES_BUCKET ?? ""; // Object Storage bucket name
const EGRESS_URL = process.env.EGRESS_URL ?? "https://example.com";
const PORT = Number(process.env.PORT ?? 8000); // matches the LB health check port

// Real internet check: fails on a timeout (5s), a network error, or a bad status.
async function fetchPublicSite(): Promise<void> {
  const res = await fetch(EGRESS_URL, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

// Real note saving. Logs in as the server itself ("instance principal"), so no
// password or key is stored. This needs the dynamic group and policy from Day 2.
async function saveNote(text: string): Promise<string> {
  // Imported here, not at the top, so local runs and tests don't load the SDK.
  const common = await import("oci-common");
  const objectstorage = await import("oci-objectstorage");

  const provider =
    await new common.InstancePrincipalsAuthenticationDetailsProviderBuilder().build();
  const client = new objectstorage.ObjectStorageClient({
    authenticationDetailsProvider: provider,
  });
  const namespaceName = (await client.getNamespace({})).value; // account-wide storage namespace
  const objectName = `note-${randomBytes(4).toString("hex")}.txt`; // random name avoids overwrites
  await client.putObject({
    namespaceName,
    bucketName: BUCKET,
    objectName,
    putObjectBody: text,
    contentLength: Buffer.byteLength(text), // bytes, not characters
  });
  return objectName;
}

// Wire the real functions in and start listening. "0.0.0.0" accepts traffic
// from other machines (the load balancer), not just localhost.
const deps: Deps = { version: VERSION, fetchPublicSite, saveNote };
createApp(deps).listen(PORT, "0.0.0.0", () => {
  console.log(`app ${VERSION} listening on ${PORT}`);
});
