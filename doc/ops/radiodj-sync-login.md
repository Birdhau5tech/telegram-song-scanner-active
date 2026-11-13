# RadioDJ DB login for the request bot (`radiodj_sync`)

The request bot runs on **xanadu** (100.74.243.72). It reads RadioDJ's library and
writes queued requests into the `radiodj2` MariaDB on the broadcast rig
(**DESKTOP-I3ANUVP**, Tailscale 100.102.251.35:3306).

## Why

As of 2026-11-13, xanadu's `.env` logged in as `root` against the rig's LAN IP
(10.0.0.193). MariaDB only allowed root from xanadu's Tailscale IP, so every
login was refused and `database_available=False`. Approved requests never
reached RadioDJ.

## Rig side: done 2026-11-13 by Claude on the i3

- Created `radiodj_sync`@`100.74.243.72` with these grants:
  - `SELECT` on `radiodj2.*`
  - `INSERT, UPDATE` on `radiodj2.queuelist` and `radiodj2.requests`
- Dropped the leftover remote `root`@`100.74.243.72`. Root is loopback-only now.
- The credentials live only on the rig, in
  `%USERPROFILE%\.fleetbridge\secrets\radiodj_sync.env` (owner and SYSTEM only).
  They are not in git or chat.

## xanadu side: TODO, any seat with SSH to xanadu

1. Find the deployed bot checkout and its `.env` (`ls ~ | grep -i scanner`).
   It may be named `whatsapp-song-scanner`. Back up the current `.env` first.
2. Copy the five `RADIODJ_DB_*` lines from the rig's secret file into that `.env`,
   replacing any `RADIODJ_DB_*` and any RadioDJ-specific root `MARIADB_*` values.
   Never paste the password into chat, issues or commits.
3. Restart the bot (docker compose / systemd / tmux, whichever is used there).
4. Verify:
   - The bot log or health check shows `database_available=True`.
   - `mariadb -h 100.102.251.35 -u radiodj_sync -p radiodj2 -e 'SELECT COUNT(*) FROM songs'`
     returns about 105.
   - An approved test request shows up in RadioDJ's queue.
5. Note the result on the tracking PR.

## Still open (needs Keath, plus an off-air window)

- MariaDB listens on `0.0.0.0:3306`. Bind it to loopback plus Tailscale.
- RadioDJ's REST plugin (`127.0.0.1:7000`) has a default password that its log
  records. Change it before exposing the plugin to xanadu.
- Rotate the rig's MariaDB root password. It was shown in an agent session log
  on 2026-11-13.
