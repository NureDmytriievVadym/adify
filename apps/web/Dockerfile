FROM node:24-bookworm-slim AS build
WORKDIR /app
RUN npm install --global npm@12.0.2
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci --ignore-scripts
COPY apps/web ./apps/web
RUN npm run build

FROM node:24-bookworm-slim AS runtime
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /app/apps/web/build ./build
COPY --from=build --chown=node:node /app/node_modules ./node_modules
USER node
EXPOSE 3000
CMD ["node", "build"]
