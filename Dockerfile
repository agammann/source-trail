# Python coordinator and inspector image.
# Supply the model runtime and weights separately.
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --chown=65532:65532 sourcetrail /app/sourcetrail
USER 65532:65532

EXPOSE 8765
ENTRYPOINT ["python", "-m", "sourcetrail"]
CMD ["--help"]
