FROM golang:1.23 AS builder
WORKDIR /app

COPY go.mod ./
COPY . .
RUN go build -o server main.go

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/server /app/server

EXPOSE 8000
CMD ["/app/server"]
