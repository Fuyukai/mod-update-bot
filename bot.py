import sys
import time

import curio
import logging
import multio
import requests
from curio.thread import AWAIT, async_thread
from curious.core.httpclient import HTTPClient
from typing import Dict
from urllib.parse import quote

multio.init("curio")
http_client = HTTPClient(token=sys.argv[1])
# manager = CommandsManager(client)
# manager.register_events()

# state
populating = True
_running = False
mods: Dict[str, str] = {}
MODS_URL = "https://mods.factorio.com/api/mods"

# channel IDs
upd_channel = 390979829907980289

logging.basicConfig(level=logging.DEBUG)


@async_thread()
def scrape_mod_portal():
    global populating

    while True:
        headers = {"user-agent": f"factorio mod notifier/1.3"}
        params = {"page_size": "max"}

        for try_ in range(0, 10):
            print("Scanning mods...")
            page = requests.get(MODS_URL, params=params, headers=headers)

            # went a page too far
            if page.status_code == 404:
                body = {"results": []}
                break

            if page.status_code != 200:
                print("Mod portal died, sleeping and retrying in a bit")
                time.sleep(5)
                continue
            else:
                body = page.json()
                break
        else:
            print("Could not download mod portal data at all. Retrying later.")
            time.sleep(300)
            continue

        already_processed = set()
        print("Processing mods...")
        for mod in body.get("results", []):
            name = mod["name"]

            # Duplicate checking...
            if name in already_processed:
                continue

            already_processed.add(name)
            latest = mod["latest_release"]

            # Check for new mods.
            if name not in mods:
                mods[name] = latest["version"]
                if not populating:
                    print("New mod:", name)
                    AWAIT(_do_send_new(mod))
                # else:
                    # print("Populating mod:", name)
            else:
                if mods[name] != latest["version"]:
                    print("Updated mod:", name)
                    mods[name] = latest["version"]
                    AWAIT(_do_send_update(mod))

        # unflip populating because we're successfully downloaded all mods
        if populating:
            populating = False
            print("Populated all mods.")

        print("Waiting 60 seconds to send mod data.")
        time.sleep(60)


async def _do_send_new(mod: dict):
    """
    Sends a NEW mod message.
    """
    modname = quote(mod['name'])
    url = f"https://mods.factorio.com/mods/{mod['owner']}/{modname}"
    msg = f"**New mod:** {mod['title']} by {mod['owner']} - <{url}>"

    await http_client.send_message(channel_id=upd_channel, content=msg)


async def _do_send_update(mod: dict):
    """
    Sends an UPDATE mod message.
    """
    modname = quote(mod['name'])
    url = f"https://mods.factorio.com/mods/{mod['owner']}/{modname}"
    msg = f"**Updated mod:** {mod['title']} (new: **{mod['latest_release']['version']}**) " \
          f"by {mod['owner']} - {url}"

    await http_client.send_message(channel_id=upd_channel, content=msg)


curio.run(scrape_mod_portal)
