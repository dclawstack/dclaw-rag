FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY . .
RUN npm run build

EXPOSE 3003

ENV NODE_ENV=production

CMD ["npm", "start"]
