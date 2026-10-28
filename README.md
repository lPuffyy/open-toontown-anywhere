# Open Toontown: Anywhere

A fork of [Open Toontown](https://github.com/open-toontown/open-toontown), the code of Disney's Toontown Online (sv1.0.47.38), made to
run the game for [Toontown: Anywhere](https://github.com/lPuffyy/toontown-anywhere): the whole server in one Docker image, and a
client that runs in a web browser.

What this fork adds (everything is on the `anywhere` branch, the default):

- **A Docker image of the whole server**: Astron, the UberDOG, three districts, a WebSocket bridge, a sign-in service and nginx.
- **[`otpy`](otpy)**: a pure-Python replacement for the compiled `libotp` and `libtoontown`, so the game runs on a plain Linux server and in a browser.
- Astron compatibility, a server-side friend manager, cross-district friends, invasions, the Districts page, fishing and quest fixes.
- The Disney classic characters are removed.

## Run the server

You need [Docker](https://docs.docker.com/get-docker/) and a copy of the game's **resources** (the art, sound and DNA files). They are
Disney's, so they are not in this repository or in the image: you supply them. The
[open-toontown/resources](https://github.com/open-toontown/resources) repository has them. The folder you mount must have `phase_3`,
`phase_4` and the rest directly inside it.

```
docker run -d --name open-toontown --restart unless-stopped -p 7380:80 \
  -v /srv/ot/resources:/ot/src/resources:ro \
  -v /srv/ot/databases:/ot/src/astron/databases \
  -v /srv/ot/data:/ot/data \
  ghcr.io/lpuffyy/open-toontown-anywhere:latest
```

Or with Compose: put the three folders next to [`docker/docker-compose.yml`](docker/docker-compose.yml) and run
`docker compose -f docker/docker-compose.yml up -d`.

Wait about two and a half minutes. The server is ready when `/srv/ot/data/logs/ai1.log`, `ai2.log` and `ai3.log` each end with `Done.`.
Only port 80 inside the container is published; do not publish Astron's own ports.

To build the image yourself instead of pulling it: `docker build -f docker/Dockerfile -t open-toontown-anywhere .`

More (mounts, staff accounts, sign-in, what is inside the image): [docker/README.md](docker/README.md).

## Play

The browser client, and the scripts that build its download packs from your resources, are in
[Toontown: Anywhere](https://github.com/lPuffyy/toontown-anywhere) (its `web/` folder).

## Running without Docker

The upstream way (Panda3D SDK, then Astron, UberDOG, a district and the client by hand from `win32`, `darwin` or `linux`) still works
for development; see the [upstream README](https://github.com/open-toontown/open-toontown#setup).

## License and credits

Open Toontown is the work of its contributors; this fork adds our own changes on top. See [LICENSE](LICENSE). Panda3D files in
`docker/overlay` keep their own license (`docker/overlay/LICENSE-Panda3D.txt`).
