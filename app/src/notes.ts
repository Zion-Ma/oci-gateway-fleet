// Everything notes needs from Object Storage. server.ts passes in the real
// version (instance principals); tests pass in a fake, so they run offline.
export interface NoteStore {
  getNamespace: () => Promise<string>; // account-wide storage namespace
  putObject: (
    namespace: string,
    bucket: string,
    objectName: string,
    body: string
  ) => Promise<void>;
}

// What createNotes gives back: the save function for the app, and a warm-up
// that server.ts calls at startup.
export interface Notes {
  saveNote: (text: string) => Promise<string>;
  warmUp: () => Promise<void>;
}

// Builds saveNote around a bucket name and a way to open the store.
// - No bucket: fail fast, before any OCI call.
// - The store is opened and the namespace read once, then reused.
// - If that first attempt fails (e.g. the IAM policy has not propagated yet),
//   the next save tries again instead of failing forever.
export function createNotes(
  bucket: string,
  openStore: () => Promise<NoteStore>,
  now: () => number = Date.now // injectable so tests get a fixed timestamp
): Notes {
  let ready: Promise<{ store: NoteStore; namespace: string }> | undefined;

  // Opens the store and reads the namespace the first time only.
  const init = () => {
    if (!ready) {
      ready = openStore()
        .then(async (store) => ({ store, namespace: await store.getNamespace() }))
        .catch((e) => {
          ready = undefined; // allow a retry on the next call
          throw e;
        });
    }
    return ready;
  };

  const requireBucket = (): void => {
    if (!bucket) throw new Error("NOTES_BUCKET is not set");
  };

  return {
    // Writes the note as note-<timestamp>.txt and returns that name.
    saveNote: async (text) => {
      requireBucket();
      const { store, namespace } = await init();
      const objectName = `note-${now()}.txt`;
      await store.putObject(namespace, bucket, objectName, text);
      return objectName;
    },
    // Startup warm-up: does nothing when no bucket is configured.
    warmUp: async () => {
      if (!bucket) return;
      await init();
    },
  };
}
