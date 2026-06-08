# Spotify "play music" tool for OpenNex

This lets the OpenNex assistant search for and control playback on your personal Spotify
account directly from chat (e.g. "play Daft Punk", "pause", "skip to the next song").

It uses Onyx's existing **Custom Tool** + **OAuth Config** infrastructure — no new backend
code is required. Set it up once through the admin UI:

## 1. Register a Spotify app

Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create an
app, and note its **Client ID** and **Client Secret**. Add a redirect URI matching your
OpenNex deployment, e.g. `https://<your-domain>/api/oauth/callback`.

## 2. Create an OAuth Config in OpenNex

In the admin panel, create a new OAuth config with:

- **Authorization URL**: `https://accounts.spotify.com/authorize`
- **Token URL**: `https://accounts.spotify.com/api/token`
- **Client ID / Client Secret**: from step 1
- **Scopes**: `user-modify-playback-state user-read-playback-state user-read-currently-playing`

## 3. Create a Custom Tool from the schema in this folder

In the admin panel's "Actions"/"Custom Tools" section, create a new tool by pasting in the
contents of [`spotify_playback_openapi.json`](./spotify_playback_openapi.json), and link it
to the OAuth config created in step 2.

## 4. Attach the tool to your assistant

Edit your OpenNex persona/assistant and enable the new Spotify tool. The first time you ask
it to play something, you'll be prompted to connect your Spotify account (OAuth flow); after
that, playback control works directly from chat.

> Note: Spotify's playback-control endpoints require an active Spotify session on one of
> your devices (the Spotify app must be open somewhere) — the API can't "wake up" Spotify
> from a fully closed state.
