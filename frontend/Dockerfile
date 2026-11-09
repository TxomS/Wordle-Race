# Stage 1: build the static site with Node.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Test image, used by `make test`: the built site plus its tests (see tests/).
FROM build AS test
CMD ["node", "--test", "tests/*.test.js"]

# Stage 2: serve it with nginx. Only the built files are copied, so the final
# image contains no Node, no sources and no node_modules.
FROM nginx:alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
