# Guide: build the images and publish them to the registry (AWS ECR)

Two images are published:

| Image | Built from | Contains | Changes |
|---|---|---|---|
| `zapik-base` | `docker/base/Dockerfile` | Debian 13 + Python 3.13.18 (by digest), tini, pip 26.3, user `app` (uid 10001) | about once a month / on CVE |
| `zapik-web` | `Dockerfile` | `zapik-base` + locked Python packages (`requirements.txt` with hashes) + app code | every release |

Both are built for `linux/amd64` and `linux/arm64`, pushed to ECR repositories with **immutable tags** and **scan on push**, and referenced **by digest**.

---

## 0. Prerequisites (once)

```bash
docker buildx version                 # Docker with buildx
aws --version                         # AWS CLI v2
aws sts get-caller-identity           # logged in to the right account
```

IAM permissions needed: `ecr:CreateRepository`, `ecr:DescribeRepositories`, `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`, `ecr:BatchGetImage`, `ecr:DescribeImages`, `ecr:DescribeImageScanFindings`.

Multi-architecture builder:

```bash
docker buildx create --name zapik --driver docker-container --use
docker buildx inspect --bootstrap
```

Variables used below:

```bash
export AWS_ACCOUNT_ID=123456789012      # your account
export AWS_REGION=eu-central-1          # your region
export REGISTRY=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

## 1. Get the code

```bash
git clone https://github.com/andrewromanchukk/black-eye.git
cd black-eye
git checkout dev
scripts/verify_pins.sh        # optional: pinned digests still match Docker Hub, lock file in sync
```

## 2. Build and test the base image locally

```bash
make base                                              # -> zapik-base:local
docker run --rm zapik-base:local python --version      # Python 3.13.18
docker run --rm zapik-base:local tini --version        # tini version 0.19.0
docker run --rm zapik-base:local pip --version         # pip 26.3
docker run --rm zapik-base:local id app                # uid=10001(app) gid=10001(app)
```

## 3. Test the whole app on it

```bash
docker compose up --build        # http://localhost:8000, panel: demo@zapik.pl / ZapikDemo2026
make test                        # 64 tests inside the container
```

Stop with `Ctrl+C`.

## 4. Push the base image

```bash
make base-push
```

The script creates the ECR repo `zapik-base` (if missing), logs in, builds amd64+arm64, pushes the tag `py3.13.18-trixie-YYYYMMDD-<git sha>` and prints:

```
BASE_IMAGE=123456789012.dkr.ecr.eu-central-1.amazonaws.com/zapik-base@sha256:…
```

Save it:

```bash
export BASE_IMAGE=$REGISTRY/zapik-base@sha256:<digest from the output>
```

## 5. Build and push the app image

```bash
make app-push        # requires BASE_IMAGE from step 4 (must be @sha256:…) and a clean git tree
```

The script creates the ECR repo `zapik-web` (if missing), builds amd64+arm64 **on top of `BASE_IMAGE`**, pushes the tag `<git sha>` and prints the digest to deploy:

```
123456789012.dkr.ecr.eu-central-1.amazonaws.com/zapik-web@sha256:…
```

## 6. Verify what is in the registry

```bash
# both architectures present
docker buildx imagetools inspect $REGISTRY/zapik-base:<tag>
docker buildx imagetools inspect $REGISTRY/zapik-web:<git sha>

# vulnerability scan summary (wait ~1 min after push)
aws ecr describe-image-scan-findings --repository-name zapik-base --image-id imageTag=<tag> \
  --region $AWS_REGION --query 'imageScanFindings.findingSeverityCounts'
aws ecr describe-image-scan-findings --repository-name zapik-web --image-id imageTag=<git sha> \
  --region $AWS_REGION --query 'imageScanFindings.findingSeverityCounts'

# pull back from the registry and run it (proves it is usable from anywhere)
docker pull $REGISTRY/zapik-web@sha256:<digest>
docker run --rm $REGISTRY/zapik-web@sha256:<digest> python -c "import django; print(django.get_version())"   # 5.2.19
```

## 7. Use it later

- **Deploy (ECS task definition):** `"image": "<registry>/zapik-web@sha256:<digest>"` — never `:latest`.
- **Database migrations** before a release (one-off task, same image):
  `python manage.py migrate --noinput`
- **Reminder scheduler** (ECS Scheduled Task, `rate(1 hour)`, same image):
  `python manage.py send_visit_reminders`
- **Next app release:** commit → `make app-push` with the same `BASE_IMAGE`.
- **Base update** (monthly / CVE): update pins in `docker/base/Dockerfile` (see `docs/base-image.md`) → step 2–4 → new `BASE_IMAGE` → step 5.

## Without the scripts (same result)

```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY

for repo in zapik-base zapik-web; do
  aws ecr create-repository --repository-name $repo --region $AWS_REGION \
    --image-tag-mutability IMMUTABLE --image-scanning-configuration scanOnPush=true || true
done

BASE_TAG=py3.13.18-trixie-$(date +%Y%m%d)-$(git rev-parse --short HEAD)
docker buildx build --platform linux/amd64,linux/arm64 --build-arg BASE_VERSION=$BASE_TAG \
  -t $REGISTRY/zapik-base:$BASE_TAG --push docker/base
BASE_IMAGE=$REGISTRY/zapik-base@$(docker buildx imagetools inspect $REGISTRY/zapik-base:$BASE_TAG --format '{{json .Manifest.Digest}}' | tr -d '"')

APP_TAG=$(git rev-parse --short=12 HEAD)
docker buildx build --platform linux/amd64,linux/arm64 --build-arg BASE_IMAGE=$BASE_IMAGE \
  -t $REGISTRY/zapik-web:$APP_TAG --push .
docker buildx imagetools inspect $REGISTRY/zapik-web:$APP_TAG --format '{{json .Manifest.Digest}}'
```

## Troubleshooting

| Error | Fix |
|---|---|
| `Version '0.19.0-3+b8' for 'tini' was not found` | Debian published a newer build: get it from `https://api.ftp-master.debian.org/madison?package=tini&s=trixie`, update `TINI_VERSION`, rebuild. |
| `Multi-platform build is not supported for the docker driver` | Create the buildx builder (step 0). |
| `tag invalid: … already exists` | Tags are immutable: base — same date+commit pushed twice; app — same commit pushed twice. Commit a change (or reuse the existing digest). |
| `Working tree is dirty` from `make app-push` | Commit or stash changes: the app tag is the git sha. |
| `BASE_IMAGE must be pinned by digest` | Use `…/zapik-base@sha256:…`, not `:tag`. |
| `no basic auth credentials` | ECR login expired (12 h): rerun the push command. |
| `toomanyrequests` from Docker Hub | `docker login` with a Docker Hub account. |
| `THESE PACKAGES DO NOT MATCH THE HASHES` | `requirements.txt` edited by hand or a package was tampered with: regenerate the lock file (`docs/build-environment.md`). |

## Other registries
Same steps work for GitHub Container Registry or Docker Hub: replace the ECR login with `docker login ghcr.io` (or `docker login`) and use `ghcr.io/<owner>/zapik-base` / `zapik-web` as image names; create the repository and immutability settings in that registry's UI.
