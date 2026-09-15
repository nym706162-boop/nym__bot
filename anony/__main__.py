# Copyright (c) 2026 by nym
# Licensed under the MIT License.
# This file is part of nym

import asyncio
import ctypes
import gc
import importlib
import signal

from keep_alive import keep_alive

from anony import (anon, app, config, db, logger,
                    stop, thumb, userbot, yt)
from anony.plugins import all_modules


# Background RAM Trimmer for Render 512MB RAM Optimization
async def auto_ram_trimmer():
    while True:
        await asyncio.sleep(300)  # Runs garbage collection every 5 minutes
        gc.collect()
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass


async def idle():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    except NotImplementedError:
        def handler(sig, frame):
            loop.call_soon_threadsafe(stop_event.set)

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    await stop_event.wait()

async def main():
    await db.connect()
    await app.boot()
    await userbot.boot()
    await anon.boot()
    await thumb.start()

    for module in all_modules:
        importlib.import_module(f"anony.plugins.{module}")
    logger.info(f"Loaded {len(all_modules)} modules.")

    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    # Start background RAM Trimmer
    asyncio.create_task(auto_ram_trimmer())

    await idle()
    await stop()


if __name__ == "__main__":
    try:
        keep_alive()
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        raise SystemExit(ex)
