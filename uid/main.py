#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from api import (
    GenerateOkPayload,
    GeneratePayload,
    InitOkPayload,
    InitPayload,
    Message,
    NodeBase,
    Reply,
    print,
)


class Node(NodeBase):
    def __init__(self):
        self.last_id = 0

    async def msg_init(self, msg: Message[InitPayload]) -> Reply[InitOkPayload]:
        return msg.src, InitOkPayload()

    async def msg_generate(
        self, msg: Message[GeneratePayload]
    ) -> Reply[GenerateOkPayload]:
        # expected time to colision at 1000 IDs/s for 3 nodes:
        # 4 days (there are 1,056,964,608 unique floats between 0 and 1)

        # from random import random
        # return msg.src, GenerateOkPayload(id=random())

        res = f"{self.node_id}-{self.last_id}"
        self.last_id += 1

        return msg.src, GenerateOkPayload(id=res)


async def main():
    n = Node()
    await n.run()


asyncio.run(main())
