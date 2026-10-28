# Running the server in Docker

This folder builds **one image that runs the whole Open Toontown server**: Astron (built from source), the UberDOG, three districts
(Toon Valley, Giggle Grove, Silly Meadow), a WebSocket bridge for the browser client, a small sign-in service, nginx, and nightly
backups. It is the same system that runs [Toontown: Anywhere](https://github.com/lPuffyy/toontown-anywhere).

The image has the game's **code**. It does **not** have the game's **resources** (the art, sound and DNA files): they belong to
Disney, they are not in this repository, and a public image must not contain them. You bring your own and mount them.

## Get the image

From the GitHub Container Registry (built by the workflow in `.github/workflows/docker.yml`):

```
docker pull ghcr.io/lpuffyy/open-toontown-anywhere:latest
```

or build it yourself from the root of this repository:

```
docker build -f docker/Dockerfile -t open-toontown-anywhere .
```

(The first build compiles Astron and takes several minutes.)

## Run it

You need a folder of the game's resources with `phase_3`, `phase_4` and the rest inside, and two empty folders for the data.

```
docker run -d --name open-toontown --restart unless-stopped -p 7380:80 \
  -v /srv/ot/resources:/ot/src/resources:ro \
  -v /srv/ot/databases:/ot/src/astron/databases \
  -v /srv/ot/data:/ot/data \
  ghcr.io/lpuffyy/open-toontown-anywhere:latest
```

or with Compose (`docker/docker-compose.yml`). Wait about **two and a half minutes** (the three districts start one after
another). Each of `/srv/ot/data/logs/ai1.log` to `ai3.log` ends with `Done.` when its district is open.

| Mount | What it holds |
|---|---|
| `/ot/src/resources` | **Required.** The game's resources. The container stops with a message if `phase_3` is missing. |
| `/ot/src/astron/databases` | The toons and accounts (Astron's YAML database). Back this up. |
| `/ot/data` | `users.json` (sign-ins), `logs/`, `backups/`. |
| `/ot/web` | Optional. The browser client's page and download packs, if you serve them from this container. |

Port **80** inside is the only port to publish: nginx serves the page and packs, and passes `/ws` (the game's WebSocket),
`/auth`, `/recover` and `/setrecovery` (sign-in) to the services behind it.

## The client

The browser client (the page, its Python glue, and the scripts that build the download packs from your resources) is in
[Toontown: Anywhere](https://github.com/lPuffyy/toontown-anywhere), in its `web/` folder.

## Notes

- **Players are ordinary.** `docker/live.prc` makes new accounts `NO_ACCESS`. To make someone staff, set `ACCESS_LEVEL` to
  `SYSTEM_ADMIN` (or `ADMIN`, `DEVELOPER`, `MODERATOR`) in their account file under `astron/databases/astrondb`, while the server is stopped.
- **Sign-in.** The sign-in service keeps `users.json` (salted PBKDF2-SHA256). The game connection itself trusts the name the page sends, so the
  server should only be reachable through nginx, never by publishing Astron's ports. See the Toontown: Anywhere docs for this limitation.
- **What is inside.** Python 3.9, Panda3D 1.11 (a development wheel), the Python side of Panda3D 1.11 in `docker/overlay/direct`
  (Panda3D's own files, with its license), our pure-Python replacement for the compiled `libotp` / `libtoontown` (`otpy/`), and Astron
  built from <https://github.com/Astron/Astron> at the commit named in the Dockerfile.
- **Optional Discord status.** If `/ot/data/discord_webhook` exists (one line, a webhook address), `docker/discord_status.py` keeps one message
  updated with the number of toons playing. It does nothing without that file.

## Game settings (no rebuild)

Settings the person running the server may want to change live in one small file, `gameconfig.json`, in the data folder
(`/ot/data/gameconfig.json`):

```
{"gag_xp_boost": 4}
```

| Setting | Default | What it does |
|---|---|---|
| `gag_xp_boost` | `4` | Multiplies the gag training points credited for each hit. The per-battle cap per track grows with it (200 times the boost). `1` is the original rate. |

The server looks at the file again every few seconds, so a change reaches the next battle without a restart. The browser game reads the same file
(served as `/gameconfig.json`) when the page starts the game, so players pick the change up the next time they load the page. A missing file, or a
missing or invalid setting, means the default. The web server serves this file to everyone, so keep secrets out of it.
