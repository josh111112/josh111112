import os
import json
import spotipy
import requests
import re
import ascii_magic
from spotipy.oauth2 import SpotifyOAuth
from github import Github
from github import Auth
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
token = os.getenv("MY_GITHUB_TOKEN")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")
auth = Auth.Token(token)
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id, client_secret, redirect_uri, scope="user-read-recently-played"))
g = Github(auth=auth)

STATS_FILE = "stats.json"


def load_stats():
    """Load cached line counts from stats.json."""
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {"lines_added": 0, "lines_removed": 0, "last_updated": None}


def save_stats(additions, deletions):
    """Save line counts to stats.json."""
    data = {
        "lines_added": additions,
        "lines_removed": deletions,
        "last_updated": datetime.now().isoformat(),
    }
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved stats: +{additions} / -{deletions}")


def get_push_additions_deletions(g, repo_name):
    """Get lines added/removed from the most recent push commit(s).

    Uses GITHUB_SHA (head commit) and the comparison API to compute the diff
    against its parent.
    """
    sha = os.getenv("GITHUB_SHA")
    if not sha:
        print("GITHUB_SHA not set, cannot compute push diff.")
        return 0, 0

    repo = g.get_repo(repo_name)
    commit = repo.get_commit(sha)

    additions = 0
    deletions = 0
    for file in commit.files:
        additions += file.additions
        deletions += file.deletions

    print(f"Push diff (commit {sha[:7]}): +{additions} / -{deletions}")
    return additions, deletions


# --- Spotify ---
results = sp.current_user_recently_played(limit=1)
track_name = "Unknown"
image_url = ""

for songs in results['items']:
    track_name = songs['track']['name']
    artist_name = songs['track']['artists'][0]['name']
    track_name = f"{track_name} by {artist_name}"
    image_url = songs['track']['album']['images'][0]['url']
    
    response = requests.get(image_url)
    with open('temp.jpg', 'wb') as f:
        f.write(response.content)
        
    output = ascii_magic.from_image('temp.jpg')
    ascii_art = output.to_image_file('temp.png')
    break

# --- GitHub ---
user = g.get_user()
repos = user.get_repos()

# total public repos
public_repos = user.public_repos
print(f"Public Repos: {public_repos}")

# most recent repo
most_recent = sorted(repos, key=lambda r: r.updated_at, reverse=True)[0]
print(f"Most Recent Repo: {most_recent.name}")
print(g.get_rate_limit())

# most used language + total commits this year
language_bytes = {}
total_commits = 0
current_year = datetime.now().year
since = datetime(current_year, 1, 1)
for repo in user.get_repos():
    # languages
    if repo.fork:
        continue
    languages = repo.get_languages()
    for lang, bytes_count in languages.items():
        language_bytes[lang] = language_bytes.get(lang, 0) + bytes_count

    # commits this year
    try:
        commits = repo.get_commits(since=since, author=user.login)
        total_commits += commits.totalCount
    except:
        pass

most_used_language = max(language_bytes, key=language_bytes.get) if language_bytes else "N/A"
print(f"Most Used Language: {most_used_language}")
print(f"Total Commits This Year: {total_commits}")

# --- Lines Added / Removed (incremental or full scan) ---
event_name = os.getenv("GITHUB_EVENT_NAME", "")
github_repo = os.getenv("GITHUB_REPOSITORY", "")

if event_name == "push":
    # INCREMENTAL: load cached stats, add this push's diff
    stats = load_stats()
    push_add, push_del = get_push_additions_deletions(g, github_repo)
    total_additions = stats["lines_added"] + push_add
    total_deletions = stats["lines_removed"] + push_del
    save_stats(total_additions, total_deletions)
    print(f"Incremental update: Lines Added: {total_additions} | Lines Removed: {total_deletions}")
else:
    # FULL SCAN: recalibrate by scanning all repos (schedule / workflow_dispatch / local)
    total_additions = 0
    total_deletions = 0
    for repo in user.get_repos():
        if repo.fork:
            continue
        try:
            stats = repo.get_stats_contributors()
            if stats:
                for contributor in stats:
                    if contributor.author.login == user.login:
                        for week in contributor.weeks:
                            if week.w.year == current_year:
                                total_additions += week.a
                                total_deletions += week.d
        except:
            pass
    save_stats(total_additions, total_deletions)
    print(f"Full scan: Lines Added: {total_additions} | Lines Removed: {total_deletions}")

g.close()

# Generate Markdown
stats_md = f"""
## My GitHub Stats

- **Public Repos:** {public_repos}
- **Most Recent Repo:** {most_recent.name}
- **Most Used Language:** {most_used_language}
- **Commits This Year:** {total_commits}
- **Lines Added:** ![Added](https://img.shields.io/badge/-{total_additions}-brightgreen?style=flat-square) | **Lines Removed:** ![Removed](https://img.shields.io/badge/-{total_deletions}-red?style=flat-square)

## Recently Played on Spotify
**{track_name}**

![My ascii art](https://github.com/josh111112/josh111112/blob/main/temp.png?raw=true)

"""

# Update README.md
with open("README.md", "r") as f:
    readme_content = f.read()

# Replace content between markers
marker_start = "<!-- START_STATS -->"
marker_end = "<!-- END_STATS -->"
pattern = re.compile(f"{marker_start}.*?{marker_end}", re.DOTALL)

if pattern.search(readme_content):
    new_readme = pattern.sub(lambda _: f"{marker_start}\n{stats_md}\n{marker_end}", readme_content)
else:
    new_readme = readme_content + f"\n{marker_start}\n{stats_md}\n{marker_end}\n"

with open("README.md", "w") as f:
    f.write(new_readme)

print("README.md updated successfully!")