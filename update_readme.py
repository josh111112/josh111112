import os
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

# most used language + total commits this year + lines added/removed
language_bytes = {}
total_commits = 0
total_additions = 0
total_deletions = 0
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

    # lines added / removed
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

most_used_language = max(language_bytes, key=language_bytes.get) if language_bytes else "N/A"
print(f"Most Used Language: {most_used_language}")
print(f"Total Commits This Year: {total_commits}")
print(f"Lines Added: {total_additions} | Lines Removed: {total_deletions}")
g.close()

# Generate Markdown
stats_md = f"""
## 📊 GitHub Stats

- **Public Repos:** {public_repos}
- **Most Recent Repo:** {most_recent.name}
- **Most Used Language:** {most_used_language}
- **Commits This Year:** {total_commits}
- **Lines Added:** {total_additions} | **Lines Removed:** {total_deletions}

## 🎵 Recently Played on Spotify
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