FROM python:3.11-alpine

# Install build dependencies & runtime dependencies
RUN apk update --no-interactive
RUN apk add --no-interactive --no-cache imagemagick ffmpeg build-base libffi-dev openssl-dev git olm olm-dev

# Install Python dependencies
RUN pip --no-input --no-color --disable-pip-version-check install --upgrade pip
RUN pip --no-input --no-color install --upgrade setuptools wheel
RUN pip --no-input --no-color install --upgrade build 'matrix-nio[e2e]' click httpx

# Install package dependencies
RUN mkdir -p /niobot/wheels
COPY .git /niobot/.git
# ^ Needed for versioning
COPY src /niobot/src
COPY pyproject.toml /niobot
COPY requirements.txt /niobot

# Build package
RUN python -m build -w -o /niobot/wheels /niobot

# Install package
RUN pip --no-input --no-color install --compile --no-warn-script-location /niobot/wheels/*.whl

CMD ["niocli", "version"]
