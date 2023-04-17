import asyncio
from dataclasses import dataclass
import dataclasses
import json
import sys
import traceback
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from api.errors import MaelstormError, MaelstormErrorCode, NotSupportedError

_og_print = print


def print(*args, **kwargs):
    _og_print(*args, **kwargs, file=sys.stderr)


async def setup_stdio():
    # alex_noname CC BY-SA 4.0 https://stackoverflow.com/a/64317899
    # - Cosmetic changes were made to code layout and variable naming
    loop = asyncio.get_running_loop()

    stdin = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stdin)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    w_transport, w_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    stdout = asyncio.StreamWriter(w_transport, w_protocol, stdin, loop)

    return stdin, stdout


@dataclass(kw_only=True)
class Payload:
    type: str
    msg_id: int | None = None
    in_reply_to: int | None = None


@dataclass(kw_only=True)
class InitPayload(Payload):
    type: Literal["init"] = "init"
    node_id: str
    node_ids: list[str]


@dataclass(kw_only=True)
class InitOkPayload(Payload):
    type: Literal["init_ok"] = "init_ok"


@dataclass(kw_only=True)
class ErrorPayload(Payload):
    type: Literal["error"] = "error"
    code: int
    text: str | None = None


PayloadT = TypeVar("PayloadT", bound=Payload)


@dataclass(frozen=True, kw_only=True)
class Message(Generic[PayloadT]):
    id: int | None = None
    src: str
    dest: str
    body: PayloadT


Reply: TypeAlias = tuple[str, PayloadT] | None

# Workload: echo


@dataclass(kw_only=True)
class EchoPayload(Payload):
    type: Literal["echo"] = "echo"
    echo: Any


@dataclass(kw_only=True)
class EchoOkPayload(Payload):
    type: Literal["echo_ok"] = "echo_ok"
    echo: Any


# Workload: unique-IDs


@dataclass(kw_only=True)
class GeneratePayload(Payload):
    type: Literal["generate"] = "generate"


@dataclass(kw_only=True)
class GenerateOkPayload(Payload):
    type: Literal["generate_ok"] = "generate_ok"
    id: Any


# Node base


class NodeBase:
    stdin: asyncio.StreamReader
    stdout: asyncio.StreamWriter
    running: bool

    node_id: str
    node_ids: list[str]

    async def run(self):
        print("Setting up I/O")
        self.stdin, self.stdout = await setup_stdio()

        running = True

        print("Starting main loop")
        while running:
            try:
                line = await self.stdin.readline()

                data: Any
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print("Failed to decode message:", line)
                    print(traceback.format_exc())
                    continue

                try:
                    body = data["body"]
                    del data["body"]

                    type_ = body["type"]

                    reply: Reply = None
                    if type_ == "init":
                        self.node_id = body["node_id"]
                        self.node_ids = body["node_ids"]

                        reply = await self.msg_init(
                            Message(**data, body=InitPayload(**body))
                        )
                    elif type_ == "error":
                        print(
                            f"!!! Error ({body['code']})"
                            + (f": {body['text']}" if body["text"] is not None else "")
                        )
                    elif type_ == "echo":
                        reply = await self.msg_echo(
                            Message(**data, body=EchoPayload(**body))
                        )
                    elif type_ == "generate":
                        reply = await self.msg_generate(
                            Message(**data, body=GeneratePayload(**body))
                        )
                    else:
                        raise NotSupportedError(f"unknown message type: {type_}")

                    if reply is not None:
                        reply_dest, reply_body = reply
                        reply_body.in_reply_to = body["msg_id"]
                        await self.send(reply_dest, reply_body)
                except MaelstormError as err:
                    await self.error(data["dest"], err.code, err.msg)
            except Exception:
                print(traceback.format_exc())
                continue

    async def send(self, dest: str, body: Payload):
        if not dest[0] == "c" and dest not in self.node_ids:
            raise ValueError("unknown destination:", dest)

        data = {
            "src": self.node_id,
            "dest": dest,
            "body": {
                k: v for k, v in dataclasses.asdict(body).items() if v is not None
            },
        }

        x = json.dumps(data) + "\n"
        self.stdout.write(x.encode())
        await self.stdout.drain()

    async def error(self, dest: str, code: MaelstormErrorCode, text: str | None = None):
        await self.send(dest, ErrorPayload(code=code.value, text=text))

    async def msg_init(self, msg: Message[InitPayload]) -> Reply[InitOkPayload]:
        raise NotSupportedError()

    async def msg_echo(self, msg: Message[EchoPayload]) -> Reply[EchoOkPayload]:
        raise NotSupportedError()

    async def msg_generate(
        self, msg: Message[GeneratePayload]
    ) -> Reply[GenerateOkPayload]:
        raise NotSupportedError()
