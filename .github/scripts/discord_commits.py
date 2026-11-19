"""Posts the commits of a push to a Discord channel, one embed per commit with the author's name and avatar.

Reads the push event from $GITHUB_EVENT_PATH (commit text is untrusted: it is only ever read as data here) and the webhook from
$DISCORD_WEBHOOK. Set DRY_RUN=1 to print the payload instead of sending it."""
import json
import os
import urllib.request

event = json.load(open(os.environ['GITHUB_EVENT_PATH'], encoding='utf-8'))
repo = event['repository']
branch = event['ref'].split('/', 2)[-1]
commits = [c for c in event.get('commits', []) if c.get('distinct', True)
           and not c['message'].startswith(('Merge pull request', 'Merge branch', 'Merge remote-tracking'))]
if not commits:
    raise SystemExit('nothing to post')


def clip(text, n):
    text = text.strip()
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'


embeds = []
for c in commits:
    title, _, body = c['message'].partition('\n')
    author = c['author']
    user = author.get('username')
    embed = {
        'author': {'name': author.get('name') or user or 'unknown'},
        'title': clip(title, 250),
        'url': c['url'],
        'description': clip(body, 400),
        'color': 0x5865F2,
        'footer': {'text': '%s · %s · %s' % (repo['name'], branch, c['id'][:7])},
        'timestamp': c['timestamp'],
    }
    if user:
        embed['author']['icon_url'] = 'https://github.com/%s.png' % user
        embed['author']['url'] = 'https://github.com/%s' % user
    embeds.append(embed)

hook = os.environ.get('DISCORD_WEBHOOK', '')
for i in range(0, len(embeds), 10):                  # Discord takes at most 10 embeds per message
    payload = {'username': 'GitHub', 'embeds': embeds[i:i + 10], 'allowed_mentions': {'parse': []}}
    if os.environ.get('DRY_RUN') == '1' or not hook:
        print(json.dumps(payload, indent=1))
        continue
    req = urllib.request.Request(hook, json.dumps(payload).encode(), {'Content-Type': 'application/json', 'User-Agent': 'commit-feed'})
    urllib.request.urlopen(req, timeout=20).read()
