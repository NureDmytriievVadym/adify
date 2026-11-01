# Development image: source is copied in, then Compose Watch keeps it in sync.
FROM node:24-bookworm-slim
RUN npm install --global npm@12.0.2
WORKDIR /app
COPY package.json package-lock.json ./
COPY frontend/package.json ./frontend/package.json
RUN npm ci --ignore-scripts
COPY eslint.config.js .prettierrc.json .prettierignore ./
COPY frontend ./frontend
EXPOSE 5173
CMD ["npm", "run", "dev", "--workspace", "@adify/web"]
