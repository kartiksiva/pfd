FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache curl

COPY package.json package.json
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
