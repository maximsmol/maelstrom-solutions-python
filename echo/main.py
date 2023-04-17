#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from api import (
    EchoOkPayload,
    EchoPayload,
    InitOkPayload,
    InitPayload,
    Message,
    NodeBase,
    Reply,
    print,
)


class Node(NodeBase):
    async def msg_init(self, msg: Message[InitPayload]) -> Reply[InitOkPayload]:
        return InitOkPayload()

    async def msg_echo(self, msg: Message[EchoPayload]) -> Reply[EchoOkPayload]:
        return EchoOkPayload(echo=msg.body.echo)


async def main():
    n = Node()
    await n.run()


asyncio.run(main())
