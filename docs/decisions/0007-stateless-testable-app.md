# 0007: Stateless app, outside pieces passed in
Date: 2026-11-10 | Day: 1 | Status: Accepted

## Context
Fleet servers can be replaced at any time. I also wanted to test the app without a network or an OCI login.

## Decision
- The app keeps no state on disk. Notes go to Object Storage.
- `createApp` takes a `Deps` object (`fetchPublicSite`, `saveNote`). Tests pass in fakes. `server.ts` passes in the real ones.
- Since 2026-11-12 the notes logic is in `src/notes.ts`, and it takes a store object the same way.
- Graceful shutdown on SIGTERM is **not in the code yet**. The systemd unit only sets `TimeoutStopSec=20`. TODO: add a SIGTERM handler that stops accepting requests and finishes the open ones.

## Why
Any server can answer any request, so I can replace servers freely. The tests need no network.

## Trade-offs
Every note write is a network call to Object Storage. Without the shutdown handler, a server that stops can cut a request in half.
