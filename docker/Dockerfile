# Open Toontown (Toontown: Anywhere fork): the whole game server in one image.
#
#   docker build -f docker/Dockerfile -t open-toontown-anywhere .
#
# The image holds the game's code, Astron, Panda3D, nginx and the small services around them. It does NOT hold the game's
# resources (the art, sound and DNA files): they are Disney's, so you supply them and mount them (see docker/README.md).

# ---- stage 1: Astron, the game's message director, state server, database server and client agent
FROM debian:bookworm-slim AS astron
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates cmake g++ make \
        libboost-all-dev libyaml-cpp-dev libuv1-dev libssl-dev pkg-config \
 && rm -rf /var/lib/apt/lists/*
ARG ASTRON_COMMIT=9a8ebc1449dc15ae69c2f1ef3176b674e656a2a0
RUN git clone https://github.com/Astron/Astron.git /src && cd /src && git checkout ${ASTRON_COMMIT}
RUN cmake -S /src -B /abuild -DCMAKE_BUILD_TYPE=Release && cd /abuild && make -j"$(nproc)" astrond

# ---- stage 2: the server (the same Debian release as stage 1, so Astron finds the libraries it was built against)
FROM python:3.9-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx libgl1 libglib2.0-0 tini libyaml-cpp0.7 libuv1 libboost-system1.74.0 libboost-filesystem1.74.0 libboost-regex1.74.0 libboost-thread1.74.0 libboost-date-time1.74.0 libboost-program-options1.74.0 libssl3 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pytz websockets \
 && pip install --no-cache-dir --pre --index-url https://archive.panda3d.org/simple/ panda3d==1.11.0.dev4085+shaderpipeline.388

# the Python side of Panda3D 1.11 (Astron support and tasks) on top of the wheel: the wheel's own copy lacks the Astron classes
COPY docker/overlay/direct /usr/local/lib/python3.9/site-packages/direct
# the pure-Python stand-ins for the compiled libotp / libtoontown, loaded into every Python process
RUN printf 'import sys\nsys.path.insert(0, "/ot/src")\ntry:\n    import otpy.install\n    otpy.install.install()\nexcept Exception as e:\n    print("otpy install failed", e, file=sys.stderr)\n' > /usr/local/lib/python3.9/site-packages/sitecustomize.py

# the game's code (see .dockerignore: no resources, no databases, no Windows files)
COPY . /ot/src
COPY --from=astron /abuild/astrond /ot/src/astron/linux/astrond
COPY docker/auth_service.py docker/wsbridge.py docker/discord_status.py docker/nginx.conf docker/run.sh /ot/
COPY docker/live.prc /ot/src/etc/live.prc
# Astron's client port is opened to the bridge inside the container only
RUN sed 's#bind: 127.0.0.1:7198#bind: 0.0.0.0:7198#' /ot/src/astron/config/astrond.yml > /ot/src/astron/config/astrond-linux.yml \
 && chmod +x /ot/run.sh /ot/src/astron/linux/astrond \
 && cp /ot/nginx.conf /etc/nginx/conf.d/default.conf && rm -f /etc/nginx/sites-enabled/default

WORKDIR /ot/src
EXPOSE 80
# resources/ is required; astron/databases/ and /ot/data keep the toons, accounts, logs and backups; /ot/web is the browser client's page and packs (optional)
VOLUME ["/ot/src/resources", "/ot/src/astron/databases", "/ot/data", "/ot/web"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/ot/run.sh"]
