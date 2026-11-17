# Guide: build the base image and push it to your registry

Covers the golden base image `zapik-base` (`docker/base/Dockerfile`) only.
Nothing in this repo creates registry repositories or pushes images automatically: you run every step yourself, into a repository **you have already created**.

## 0. Prerequisites

```bash
docker buildx version
aws sts get-caller-identity              # if the registry is ECR
```

Multi-architecture builder (once, needed to build amd64 + arm64 together):

```bash
docker buildx create --name zapik --driver docker-container --use
docker buildx inspect --bootstrap
```

## 1. Get the code

```bash
git clone https://github.com/andrewromanchukk/black-eye.git
cd black-eye
git checkout dev
```

## 2. Build and check locally

```bash
docker build -t zapik-base:local docker/base        # or: make base
docker run --rm zapik-base:local python --version   # Python 3.13.18
docker run --rm zapik-base:local tini --version     # tini version 0.19.0
docker run --rm zapik-base:local pip --version      # pip 26.3
docker run --rm zapik-base:local id app             # uid=10001(app) gid=10001(app)
```

## 3. Push to your existing repository

```bash
REPO=<your registry>/<your repository>     # e.g. 123456789012.dkr.ecr.eu-central-1.amazonaws.com/zapik-base
TAG=py3.13.18-trixie-$(date +%Y%m%d)

# log in (ECR example)
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <registry>

docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg BASE_VERSION=$TAG \
  -t $REPO:$TAG --push docker/base
```

## 4. Get the digest (use it, not the tag)

```bash
docker buildx imagetools inspect $REPO:$TAG                                   # amd64 + arm64 listed
docker buildx imagetools inspect $REPO:$TAG --format '{{json .Manifest.Digest}}'
```

Reference the base later as `$REPO@sha256:<digest>`, e.g. `docker build --build-arg BASE_IMAGE=$REPO@sha256:<digest> .` for the app image.

## Troubleshooting

| Error | Fix |
|---|---|
| `Version '0.19.0-3+b8' for 'tini' was not found` | Debian published a newer build: get it from `https://api.ftp-master.debian.org/madison?package=tini&s=trixie`, update `TINI_VERSION` in `docker/base/Dockerfile`, rebuild. |
| `Multi-platform build is not supported for the docker driver` | Create the buildx builder (step 0). |
| `tag … already exists` | The repository has immutable tags: use a new tag. |
| `no basic auth credentials` | Login expired (ECR: 12 h): log in again. |
| `toomanyrequests` from Docker Hub | `docker login` with a Docker Hub account. |
