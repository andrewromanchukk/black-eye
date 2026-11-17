# Інструкція: ручна збірка базового образу `zapik-base`

Образ описано в `docker/base/Dockerfile`. Скриптів, цілей Makefile чи сервісу compose, які збирають або публікують образ, у проєкті немає: збірку й публікацію ви виконуєте самі. Публікувати можна лише в репозиторій, який **ви вже створили**.

`docker compose up` образ не збирає. Він бере готовий образ, ім'я якого задано у змінній `BASE_IMAGE` (за замовчуванням `zapik-base:local`). Тому перед першим запуском його треба зібрати (крок 2) або завантажити з реєстру (крок 5).

## 0. Що потрібно

```bash
docker version
docker buildx version     # потрібен лише для збірки під кілька архітектур (крок 3)
```

## 1. Отримати код

```bash
git clone https://github.com/andrewromanchukk/black-eye.git
cd black-eye
git checkout dev
```

## 2. Зібрати образ і перевірити його

```bash
TAG=py3.13.18-trixie-$(date +%Y%m%d)-$(git rev-parse --short HEAD)

docker build --build-arg BASE_VERSION=$TAG -t zapik-base:local docker/base

docker run --rm zapik-base:local python --version   # Python 3.13.18
docker run --rm zapik-base:local tini --version     # tini version 0.19.0
docker run --rm zapik-base:local pip --version      # pip 26.3
docker run --rm zapik-base:local id app             # uid=10001(app) gid=10001(app)
```

`BASE_VERSION` записується в мітку `org.opencontainers.image.version`. Якщо параметр не передати, мітка матиме значення `dev`.

Після цього можна запускати застосунок: `docker compose up --build`.

## 3. Опублікувати в реєстр

Варіант А — одна архітектура (та, на якій ви збирали):

```bash
REPO=<реєстр>/<репозиторій>     # напр. docker.io/<user>/zapik-base або <account>.dkr.ecr.<region>.amazonaws.com/zapik-base

docker login <реєстр>           # Docker Hub: docker login -u <user>, пароль — Personal Access Token
                                # ECR: aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <реєстр>
docker tag zapik-base:local $REPO:$TAG
docker push $REPO:$TAG
```

Варіант Б — amd64 і arm64 разом. Потрібні buildx і QEMU; збірка і публікація відбуваються однією командою:

```bash
docker buildx create --name zapik --driver docker-container --use   # один раз
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg BASE_VERSION=$TAG \
  -t $REPO:$TAG --push docker/base
```

## 4. Отримати digest

Посилайтеся на образ за digest, а не за тегом: тег можна перезаписати, digest — ні.

```bash
docker buildx imagetools inspect $REPO:$TAG
docker buildx imagetools inspect $REPO:$TAG --format '{{json .Manifest.Digest}}'
```

## 5. Використати опублікований образ

```bash
docker pull $REPO:$TAG@sha256:<digest>
BASE_IMAGE=$REPO:$TAG@sha256:<digest> docker compose up --build
# або без compose:
docker build --build-arg BASE_IMAGE=$REPO:$TAG@sha256:<digest> -t zapik-web .
```

## Проблеми

| Помилка | Що робити |
|---|---|
| `pull access denied for zapik-base` / `zapik-base:local: not found` під час `docker compose up` | Базовий образ ще не зібрано: виконайте крок 2 або задайте `BASE_IMAGE`. |
| `Version '0.19.0-3+b8' for 'tini' was not found` | Debian випустив новішу збірку tini. Знайдіть її номер на `https://api.ftp-master.debian.org/madison?package=tini&s=trixie`, оновіть `TINI_VERSION` у `docker/base/Dockerfile` і зберіть образ знову. |
| `Multi-platform build is not supported for the docker driver` | Створіть buildx builder (крок 3, варіант Б). |
| `tag … already exists` | У репозиторії незмінні теги: використайте новий тег. |
| `no basic auth credentials` / `unauthorized` | Ви не залогінені або сесія вийшла (в ECR вона діє 12 год): виконайте `docker login` ще раз. |
| `toomanyrequests` від Docker Hub | Виконайте `docker login` з акаунтом Docker Hub. |
