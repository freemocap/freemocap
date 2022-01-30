# syntax=docker/dockerfile:1.2

# Good base image to start from for most development
FROM python:3.8-slim

# Please remember, the base image we use /must be as small as possible/ for the best
# production deployments. This is not optional.

WORKDIR /workspace

# Allows python to stream logs rather than buffer them for output.
ENV PYTHONUNBUFFERED=1

# The official Debian/Ubuntu Docker Image automatically removes the cache by default!
# Removing the docker-clean file manages that issue.
RUN rm -rf /etc/apt/apt.conf.d/docker-clean

COPY ./bin/builds/ .

# Apt-get install packages here since we're using Debian as a root OS for this particular Dockerfile.
RUN --mount=type=cache,target=/var/cache/apt ./install_packages \
    dumb-init \
    tk \
    libgl1-mesa-glx \
    libglib2.0-0 \
    imagemagick


# Install pip packages
ENV PATH=/root/.local/bin:$PATH
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip \
    && pip install -r requirements.txt

# Switch to non-root user
RUN useradd -m appuser && chown -R appuser /workspace
USER appuser

# Copy project files
COPY src/api ./api
COPY freemocap ./freemocap
COPY ./bin ./bin
COPY ./src ./src

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["./bin/run_web_server.sh"]
