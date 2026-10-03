FROM golang:1.24-alpine AS build

ARG RELEASE
ENV CGO_ENABLED=0 GOTOOLCHAIN=auto
RUN apk add --no-cache git
RUN git clone --depth 1 --branch "$RELEASE" https://github.com/minio/minio.git /src
WORKDIR /src
RUN go build -trimpath -ldflags "$(go run buildscripts/gen-ldflags.go)" -o /minio .

FROM alpine:3.22

COPY --from=build /minio /usr/bin/minio
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
