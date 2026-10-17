FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnucobol python3 make gcc libc6-dev git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN make build && make test && make doctor capture-baseline
CMD ["make", "baseline"]
