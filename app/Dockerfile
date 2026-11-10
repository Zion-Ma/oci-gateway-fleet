# ---- Stage 1: build ----
# Full dependency install + TypeScript compile. Nothing from this stage
# except /app/dist ends up in the final image.
FROM node:22-slim AS build
WORKDIR /app

# Copy manifests first so the `npm ci` layer is cached until dependencies change
COPY package*.json ./
RUN npm ci

# Copy sources after install so code edits don't invalidate the dependency cache
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# ---- Stage 2: runtime ----
# Fresh slim image: production deps + compiled JS only (no TypeScript, no devDependencies)
FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production

# Install only runtime dependencies
COPY package*.json ./
RUN npm ci --omit=dev

# Bring in the compiled output from the build stage
COPY --from=build /app/dist ./dist

# Start the gateway app
CMD ["node", "dist/server.js"]
