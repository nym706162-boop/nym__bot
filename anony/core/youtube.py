# Copyright (c) 2026 by nym
# Licensed under the MIT License.
# This file is part of nym

import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path

from py_yt import Playlist, VideosSearch

from anony import logger, config, db, app
from anony.helpers import Track, utils


class DummyLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "anony/cookies"
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

    def get_cookies(self):
        if not self.checked:
            if os.path.exists(self.cookie_dir):
                for file in os.listdir(self.cookie_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads may fail due to YouTube restrictions.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        async with aiohttp.ClientSession() as session:
            for url in urls:
                name = url.split("/")[-1]
                link = "https://batbin.me/raw/" + name
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(f"{self.cookie_dir}/{name}.txt", "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            _search = VideosSearch(query, limit=1, with_live=False)
            results = await _search.next()
        except Exception:
            return None
        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except Exception:
            pass
        return tracks

    async def _cache_to_telegram(self, video_id: str, file_path: str, video: bool) -> None:
        try:
            log_id = (
                getattr(config, "LOGGER_ID", None)
                or getattr(config, "LOG_ID", None)
                or getattr(config, "LOG_GROUP_ID", None)
            )
            if not log_id or not os.path.exists(file_path):
                return

            file_id = None
            if video:
                sent = await app.send_video(
                    chat_id=log_id,
                    video=file_path,
                    caption=f"🎥 Cached Video ID: `{video_id}`",
                )
                if sent:
                    if sent.video:
                        file_id = sent.video.file_id
                    elif sent.document:
                        file_id = sent.document.file_id
            else:
                sent = await app.send_audio(
                    chat_id=log_id,
                    audio=file_path,
                    caption=f"🎵 Cached Audio ID: `{video_id}`",
                )
                if sent:
                    if sent.audio:
                        file_id = sent.audio.file_id
                    elif sent.document:
                        file_id = sent.document.file_id

            if file_id:
                await db.add_cached_track(video_id, file_id)
                logger.info(f"Successfully cached {video_id} to Telegram Log Channel.")
        except Exception as e:
            logger.error(f"Error caching track to Telegram: {e}")

    async def download(self, video_id: str, video: bool = False) -> str | None:
        ext = "mp4" if video else "webm"
        filename = f"downloads/{video_id}.{ext}"

        if Path(filename).exists():
            logger.info(f"Local Cache Hit: {filename}")
            return filename

        try:
            cached_file_id = await db.get_cached_track(video_id)
            if cached_file_id:
                logger.info(f"Telegram Channel Cache Hit for {video_id}")
                return cached_file_id
        except Exception:
            pass

        url = self.base + video_id
        cookie = self.get_cookies()

        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "logger": DummyLogger(),
            "nocheckcertificate": True,
            "cookiefile": cookie,
            "concurrent_fragment_downloads": 3,  # ආරක්ෂිත සහ ස්ථාවර අගයක්
            "socket_timeout": 60,
            "retries": 10,
            "fragment_retries": 10,
        }

        if video:
            ydl_opts = {
                **base_opts,
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+bestaudio/best[ext=mp4]/best",
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": "bestaudio/best",
            }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except Exception as ex:
                    logger.error("Download failed for %s: %s", video_id, ex)
                    return None
            return filename

        downloaded_file = await asyncio.to_thread(_download)

        if downloaded_file and os.path.exists(downloaded_file):
            asyncio.create_task(self._cache_to_telegram(video_id, downloaded_file, video))

        return downloaded_file

    async def get_stream_url(self, video_id: str) -> str | None:
        url = self.base + video_id
        cookie = self.get_cookies()
        
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "logger": DummyLogger(),
            "nocheckcertificate": True,
            "cookiefile": cookie,
        }

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    return info.get("url")
                except Exception:
                    return None

        return await asyncio.to_thread(_extract)
