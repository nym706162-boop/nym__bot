<div align="center">

<h2>nym Music Bot</h2>

<b>Telegram Group Calls Streaming Bot</b><br>
Supports YouTube, Spotify, Resso, Apple Music, SoundCloud and M3U8 links.

<a href="https://github.com/nym706162-boop/nym__bot/stargazers">
    <img src="https://img.shields.io/github/stars/nym706162-boop/nym__bot?color=blueviolet&logo=github&logoColor=black&style=for-the-badge" alt="Stars"/>
</a>
<a href="https://github.com/nym706162-boop/nym__bot/network/members">
    <img src="https://img.shields.io/github/forks/nym706162-boop/nym__bot?color=blueviolet&logo=github&logoColor=black&style=for-the-badge" alt="Forks"/>
</a>
<a href="https://github.com/nym706162-boop/nym__bot/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"/>
</a>
<a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Written%20in-Python-blue?style=for-the-badge&logo=python" alt="Python"/>
</a>
<br>

<img src="https://github.com/nym706162-boop/nym__bot/blob/master/.github/anonx.jpg" width="720" height="auto">

nym Music Bot lets you stream high-quality and low-latency audio and video playback into telegram group video chats.<br>
Built with Python, Pyrogram, and Py-TgCalls, it’s optimized for reliability and easy deployment on Heroku, VPS, Render or Docker.
</div>

<hr>

<h2>🔥 Features</h2>

- 🎧 Stream low-latency audio in real time to <b>Telegram group video chats</b>
- 🌐 Supports multiple platforms like <b>YouTube, Spotify, Apple Music, SoundCloud</b>
- ⚡ Advanced queue management with auto-play
- ⚙️ Easy deployment — works on Local, VPS, Render or Heroku
- ❤️ Built with Python

<hr>

<h2>☁️ Deployment Options</h2>

<h3>✔️ Prerequisites</h3>

- <a href="https://www.python.org">Python 3.10+</a> installed  
- <a href="https://deno.com/">deno</a> & <a href="https://ffmpeg.org/">ffmpeg</a> installed on your system  
- Required variables mentioned in <a href="https://github.com/nym706162-boop/nym__bot/blob/master/sample.env">sample.env</a>

<details>
    <summary>
        <h3>Local / VPS Setup</h3>
    </summary>

<h4>🐧 Linux / macOS</h4>

```bash
git clone [https://github.com/nym706162-boop/nym__bot](https://github.com/nym706162-boop/nym__bot) && cd nym__bot

# Install uv
curl -Ls [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
export PATH="$HOME/.local/bin:$PATH"

# Install dependencies
uv sync --frozen

# Rename and configure environment variables
mv sample.env .env
# Edit .env with your credentials

# Start the bot
bash start
