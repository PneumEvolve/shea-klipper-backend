# routers/ws_manager.py
# Shared WebSocket room manager — used by all multiplayer games.
# Pure in-memory relay. No DB writes, no Supabase, no cost.

from collections import defaultdict
from fastapi import WebSocket
import logging

logger = logging.getLogger("ws_manager")


class RoomManager:
    def __init__(self, game_name: str):
        self.game_name = game_name
        # room_id -> list of connected WebSockets
        self._rooms: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, room_key: str, websocket: WebSocket):
        await websocket.accept()
        self._rooms[room_key].append(websocket)
        peer_count = len(self._rooms[room_key])
        logger.info(f"[{self.game_name}] ws connect room={room_key} peers={peer_count}")
        return peer_count  # caller can use this to know if they're p1 or p2

    def disconnect(self, room_key: str, websocket: WebSocket):
        if room_key in self._rooms:
            try:
                self._rooms[room_key].remove(websocket)
            except ValueError:
                pass
            if not self._rooms[room_key]:
                del self._rooms[room_key]
                logger.info(f"[{self.game_name}] room closed room={room_key}")
            else:
                logger.info(f"[{self.game_name}] ws disconnect room={room_key} peers_remaining={len(self._rooms[room_key])}")

    async def relay(self, room_key: str, sender: WebSocket, message: str):
        """Forward message to every peer in the room except the sender."""
        peers = self._rooms.get(room_key, [])
        dead = []
        for peer in peers:
            if peer is sender:
                continue
            try:
                await peer.send_text(message)
            except Exception:
                dead.append(peer)
        # Clean up any broken connections found during relay
        for peer in dead:
            self.disconnect(room_key, peer)

    def peer_count(self, room_key: str) -> int:
        return len(self._rooms.get(room_key, []))