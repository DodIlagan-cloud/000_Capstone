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

RUN python3 -m venv /opt/stats/runtime \
    && /opt/stats/runtime/bin/pip install --no-cache-dir \
        -r /requirements/identity.txt \
        -r /requirements/file-validation.txt \
        -r /requirements/document-parsing.txt

COPY modules/identity-access-module/ /app/modules/identity-access-module/
COPY modules/file-validation-module/ /app/modules/file-validation-module/
COPY modules/document-parsing-module/ /app/modules/document-parsing-module/
COPY --from=dotnet-build /app/stats-web /app/stats-web
COPY infrastructure/containers/stats/start-stats-runtime.sh /app/start-stats-runtime.sh

RUN /usr/bin/tesseract --version \
    && /opt/stats/runtime/bin/python -c "import fitz; import pytesseract; from PIL import Image; print('M5 OCR runtime dependencies available')" \
    && chmod +x /app/start-stats-runtime.sh

ENV PATH="/opt/stats/runtime/bin:${PATH}"
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV OCR_ENGINE=tesseract
ENV ALLOW_OCR_FALLBACK=true
ENV OCR_LANGUAGES=eng

EXPOSE 8080

ENTRYPOINT ["/app/start-stats-runtime.sh"]

# M13 End
