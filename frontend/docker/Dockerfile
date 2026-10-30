# Source is bind-mounted by docker-compose.yml.
FROM node:24-bookworm-slim
RUN npm install --global npm@12.0.2
WORKDIR /app
COPY package.json package-lock.json ./
COPY frontend/package.json ./frontend/package.json
RUN npm ci --ignore-scripts
EXPOSE 5173
CMD ["npm", "run", "dev", "--workspace", "@adify/web"]
