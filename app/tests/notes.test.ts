import { createNotes, NoteStore } from "../src/notes";

// A fake store that records calls, so tests never touch OCI.
function makeStore() {
  const calls = { open: 0, getNamespace: 0, puts: [] as string[][] };
  const openStore = async (): Promise<NoteStore> => {
    calls.open++;
    return {
      getNamespace: async () => {
        calls.getNamespace++;
        return "ns1";
      },
      putObject: async (ns, bucket, name, body) => {
        calls.puts.push([ns, bucket, name, body]);
      },
    };
  };
  return { calls, openStore };
}

test("saveNote fails fast when NOTES_BUCKET is unset (no OCI call)", async () => {
  const { calls, openStore } = makeStore();
  const { saveNote, warmUp } = createNotes("", openStore);
  await expect(saveNote("hi")).rejects.toThrow("NOTES_BUCKET");
  await warmUp(); // also a no-op without a bucket
  expect(calls.open).toBe(0);
  expect(calls.getNamespace).toBe(0);
});

test("saveNote writes note-<timestamp>.txt and returns the name", async () => {
  const { calls, openStore } = makeStore();
  const { saveNote } = createNotes("notes", openStore, () => 1700000000000);
  expect(await saveNote("hello")).toBe("note-1700000000000.txt");
  expect(calls.puts).toEqual([["ns1", "notes", "note-1700000000000.txt", "hello"]]);
});

test("namespace is fetched once, even across warm-up and many saves", async () => {
  const { calls, openStore } = makeStore();
  const { saveNote, warmUp } = createNotes("notes", openStore);
  await warmUp();
  await saveNote("a");
  await saveNote("b");
  expect(calls.open).toBe(1);
  expect(calls.getNamespace).toBe(1);
});

test("a failed startup is retried on the next save", async () => {
  let attempts = 0;
  const openStore = async (): Promise<NoteStore> => {
    attempts++;
    if (attempts === 1) throw new Error("policy not ready");
    return { getNamespace: async () => "ns1", putObject: async () => {} };
  };
  const { saveNote, warmUp } = createNotes("notes", openStore);
  await expect(warmUp()).rejects.toThrow("policy not ready");
  expect(await saveNote("x")).toMatch(/^note-\d+\.txt$/);
});
