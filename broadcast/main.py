#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from api import (
    BroadcastOkPayload,
    BroadcastPayload,
    InitOkPayload,
    InitPayload,
    Message,
    NodeBase,
    ReadOkPayload,
    ReadPayload,
    Reply,
    TopologyOkPayload,
    TopologyPayload,
    print,
)


class Node(NodeBase):
    neighbors: list[str]

    def __init__(self):
        self.messages: set[Any] = set()

    async def msg_init(self, msg: Message[InitPayload]) -> Reply[InitOkPayload]:
        return msg.src, InitOkPayload()

    async def msg_topology(
        self, msg: Message[TopologyPayload]
    ) -> Reply[TopologyOkPayload]:
        self.neighbors = msg.body.topology[self.node_id]

        return msg.src, TopologyOkPayload()

    async def msg_broadcast(
        self, msg: Message[BroadcastPayload]
    ) -> Reply[BroadcastOkPayload]:
        # if we receive a new message, re-broadcast it to all neighbors

        if msg.body.message not in self.messages:
            self.messages.add(msg.body.message)
            await asyncio.gather(*(self.send(x, msg.body) for x in self.neighbors))

        return msg.src, BroadcastOkPayload()

    async def msg_broadcast_ok(self, msg: Message[BroadcastOkPayload]) -> None:
        ...

    async def msg_read(self, msg: Message[ReadPayload]) -> Reply[ReadOkPayload]:
        return msg.src, ReadOkPayload(messages=list(self.messages))


async def main():
    n = Node()
    await n.run()


asyncio.run(main())
