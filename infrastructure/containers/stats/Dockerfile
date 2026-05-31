# M13 - Containerization Start
# Builds the single Stats runtime image: Stats Web, module APIs, Tesseract OCR, and Python OCR dependencies.

FROM mcr.microsoft.com/dotnet/sdk:9.0-bookworm-slim AS dotnet-build

WORKDIR /build

COPY apps/stats-web/stats.Web.csproj ./
RUN dotnet restore stats.Web.csproj

COPY apps/stats-web/ ./
RUN dotnet publish stats.Web.csproj --configuration Release --output /app/stats-web --no-restore --no-self-contained

FROM mcr.microsoft.com/dotnet/aspnet:9.0-bookworm-slim AS stats-runtime

LABEL maintainer="Stats Capstone Project"
LABEL description="Single Stats runtime container: Stats Web, module APIs, Tesseract OCR"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY modules/identity-access-module/requirements.txt /requirements/identity.txt
COPY modules/file-validation-module/requirements.txt /requirements/file-validation.txt
COPY modules/document-parsing-module/requirements.txt /requirements/document-parsing.txt
COPY modules/transaction-extraction-module/requirements.txt /requirements/transaction-extraction.txt
COPY modules/data-validation-module/requirements.txt /requirements/data-validation.txt

RUN python3 -m venv /opt/stats/runtime \
    && /opt/stats/runtime/bin/pip install --no-cache-dir \
        -r /requirements/identity.txt \
        -r /requirements/file-validation.txt \
        -r /requirements/document-parsing.txt \
        -r /requirements/transaction-extraction.txt \
        -r /requirements/data-validation.txt

COPY modules/identity-access-module/ /app/modules/identity-access-module/
COPY modules/file-validation-module/ /app/modules/file-validation-module/
COPY modules/document-parsing-module/ /app/modules/document-parsing-module/
COPY modules/transaction-extraction-module/ /app/modules/transaction-extraction-module/
COPY modules/data-validation-module/ /app/modules/data-validation-module/
COPY config/ /app/config/
COPY tests/ /app/tests/
COPY README.md /app/README.md
COPY docs/ /app/docs/
COPY apps/README.md /app/apps/README.md
COPY modules/README.md /app/modules/README.md
COPY contracts/README.md /app/contracts/README.md
COPY infrastructure/README.md /app/infrastructure/README.md
COPY samples/README.md /app/samples/README.md
COPY .gitignore /app/.gitignore
COPY infrastructure/containers/stats/Dockerfile /app/infrastructure/containers/stats/Dockerfile
COPY infrastructure/containers/stats/.env.container.example /app/infrastructure/containers/stats/.env.container.example
COPY infrastructure/containers/stats/start-stats-runtime.sh /app/infrastructure/containers/stats/start-stats-runtime.sh
COPY infrastructure/compose/stats-runtime.compose.yml /app/infrastructure/compose/stats-runtime.compose.yml
COPY apps/stats-web/Program.cs /app/apps/stats-web/Program.cs
COPY apps/stats-web/appsettings.json /app/apps/stats-web/appsettings.json
COPY --from=dotnet-build /app/stats-web /app/stats-web
COPY infrastructure/containers/stats/start-stats-runtime.sh /app/start-stats-runtime.sh

RUN /usr/bin/tesseract --version \
    && /opt/stats/runtime/bin/python -c "import fitz; import pytesseract; from PIL import Image; print('M5 OCR runtime dependencies available')" \
    && chmod +x /app/start-stats-runtime.sh

ENV PATH="/opt/stats/runtime/bin:${PATH}"
ENV STATS_APP_ROOT=/app
ENV STATS_RUNTIME_CONFIG=/app/config/stats.runtime.json
ENV STATS_PATHS_CONFIG=/app/config/stats.paths.json
ENV STATS_LOGGING_CONFIG=/app/config/stats.logging.json
ENV STATS_STORAGE_PROVIDER=LocalFileSystem
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV OCR_ENGINE=tesseract
ENV ALLOW_OCR_FALLBACK=true
ENV OCR_LANGUAGES=eng

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -sf "http://localhost:${STATS_WEB_PORT:-8080}/health" || exit 1

ENTRYPOINT ["/app/start-stats-runtime.sh"]

# M13 End
