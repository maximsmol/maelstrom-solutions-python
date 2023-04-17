#!/usr/bin/env python3

from dataclasses import dataclass
import random
import sys
from pathlib import Path
from typing import Any, Literal

from ..api.errors import TimeoutError_

sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from api import (
    BroadcastOkPayload,
    BroadcastPayload,
    InitOkPayload,
    InitPayload,
    Message,
    NodeBase,
    Payload,
    ReadOkPayload,
    ReadPayload,
    Reply,
    TopologyOkPayload,
    TopologyPayload,
    print,
)


@dataclass(kw_only=True)
class CustomSyncPayload(Payload):
    type: Literal["custom_sync"] = "custom_sync"
    my_length: int


@dataclass(kw_only=True)
class CustomSyncOkPayload(Payload):
    type: Literal["custom_sync_ok"] = "custom_sync_ok"
    my_messages: list[int] | None = None


class Node(NodeBase):
    neighbors: list[str]
    census: list[str]

    def __init__(self):
        self.messages: set[Any] = set()

    async def msg_init(self, msg: Message[InitPayload]) -> Reply[InitOkPayload]:
        num_nodes = len(msg.body.node_ids)
        census_size = num_nodes // 2 + 1

        nodes = [x for x in msg.body.node_ids if x != self.node_id]
        random.shuffle(nodes)
        self.census = nodes[:census_size]

        return InitOkPayload()

    async def msg_topology(
        self, msg: Message[TopologyPayload]
    ) -> Reply[TopologyOkPayload]:
        self.neighbors = msg.body.topology[self.node_id]
        return TopologyOkPayload()

    async def msg_broadcast(
        self, msg: Message[BroadcastPayload]
    ) -> Reply[BroadcastOkPayload]:
        # if we receive a new message, re-broadcast it to all neighbors

        if msg.body.message not in self.messages:
            self.messages.add(msg.body.message)
            await asyncio.gather(*(self.send(x, msg.body) for x in self.neighbors))

        return BroadcastOkPayload()

    async def msg_broadcast_ok(self, msg: Message[BroadcastOkPayload]) -> None:
        ...

    async def msg_custom_sync(
        self, msg: Message[CustomSyncPayload]
    ) -> Reply[CustomSyncOkPayload]:
        if msg.body.my_length >= len(self.messages):
            return CustomSyncOkPayload()

        return CustomSyncOkPayload(my_messages=list(self.messages))

    async def sync_with(self, node_id: str):
        try:
            data = await self.communicate(
                CustomSyncOkPayload,
                node_id,
                CustomSyncPayload(my_length=len(self.messages)),
                timeout=1,
            )
        except TimeoutError_:
            return

        if data.my_messages is None:
            return

        self.messages |= set(data.my_messages)

    async def msg_read(self, msg: Message[ReadPayload]) -> Reply[ReadOkPayload]:
        await asyncio.gather(*(self.sync_with(x) for x in self.census))

        return ReadOkPayload(messages=list(self.messages))


async def main():
    n = Node()
    await n.run()


asyncio.run(main())
