import asyncio
from dataclasses import dataclass
import dataclasses
from inspect import get_annotations, getmembers, ismethod
import json
import sys
import traceback
from typing import Any, Generic, Literal, TypeAlias, TypeVar, get_args

from api.errors import MaelstormError, MaelstormErrorCode, NotSupportedError

_og_print = print

PayloadBodyFieldPrimitive: TypeAlias = int | float | str | bool | None
PayloadBodyField = (
    PayloadBodyFieldPrimitive
    | list[PayloadBodyFieldPrimitive]
    | dict[str, PayloadBodyFieldPrimitive]
)


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


Reply: TypeAlias = PayloadT | None

# Workload: echo


@dataclass(kw_only=True)
class EchoPayload(Payload):
    type: Literal["echo"] = "echo"
    echo: PayloadBodyField


@dataclass(kw_only=True)
class EchoOkPayload(Payload):
    type: Literal["echo_ok"] = "echo_ok"
    echo: PayloadBodyField


# Workload: unique-IDs


@dataclass(kw_only=True)
class GeneratePayload(Payload):
    type: Literal["generate"] = "generate"


@dataclass(kw_only=True)
class GenerateOkPayload(Payload):
    type: Literal["generate_ok"] = "generate_ok"
    id: PayloadBodyField


# Workload: broadcast


@dataclass(kw_only=True)
class TopologyPayload(Payload):
    type: Literal["topology"] = "topology"
    topology: dict[str, list[str]]


@dataclass(kw_only=True)
class TopologyOkPayload(Payload):
    type: Literal["topology_ok"] = "topology_ok"


@dataclass(kw_only=True)
class BroadcastPayload(Payload):
    type: Literal["broadcast"] = "broadcast"
    message: PayloadBodyField


@dataclass(kw_only=True)
class BroadcastOkPayload(Payload):
    type: Literal["broadcast_ok"] = "broadcast_ok"


@dataclass(kw_only=True)
class ReadPayload(Payload):
    type: Literal["read"] = "read"


@dataclass(kw_only=True)
class ReadOkPayload(Payload):
    type: Literal["read_ok"] = "read_ok"
    messages: list[PayloadBodyField]


# Node base


class NodeBase:
    stdin: asyncio.StreamReader
    stdout: asyncio.StreamWriter
    running: bool

    node_id: str = None
    node_idx: int
    node_ids: list[str]

    last_msg_id: int = 0
    receives_waiting: dict[int, tuple[asyncio.Event, Any]] = {}

    async def run(self):
        print("Setting up I/O")
        self.stdin, self.stdout = await setup_stdio()

        running = True

        methods = {
            name[len("msg_") :]: f
            for name, f in getmembers(
                self, lambda x: ismethod(x) and x.__name__.startswith("msg_")
            )
        }

        async def process_line(line: bytes):
            try:
                data: Any
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print("Failed to decode message:", line)
                    print(traceback.format_exc())
                    return

                try:
                    body = data["body"]
                    del data["body"]

                    type_ = body["type"]
                    if type_ == "init":
                        self.node_id = body["node_id"]
                        self.node_ids = body["node_ids"]
                        self.node_idx = self.node_ids.index(self.node_id)
                    elif type_ == "error":
                        print(
                            f"!!! Error ({body['code']})"
                            + (f": {body['text']}" if body["text"] is not None else "")
                        )

                    in_reply_to = body.get("in_reply_to")
                    rec = (
                        self.receives_waiting.get(in_reply_to)
                        if in_reply_to is not None
                        else None
                    )
                    if rec is not None:
                        self.receives_waiting[in_reply_to] = (rec[0], body)
                        rec[0].set()

                        return

                    handler = methods.get(type_)
                    if handler is None:
                        raise NotSupportedError(f"unknown message type: {type_}")

                    payload_cls = get_args(get_annotations(handler)["msg"])[0]
                    reply: Reply[Payload] = await handler(
                        Message(**data, body=payload_cls(**body))
                    )

                    if reply is not None:
                        reply.in_reply_to = body["msg_id"]
                        await self.send(data["src"], reply)
                except MaelstormError as err:
                    print("!!! Internal error:", err)
                    await self.error(data["dest"], err.code, err.msg)
            except Exception:
                print(traceback.format_exc())

        print("Starting main loop")
        while running:
            try:
                line = await self.stdin.readline()

                asyncio.create_task(process_line(line))
            except Exception:
                print(traceback.format_exc())
                continue

    async def send(self, dest: str, body: Payload, *, msg_id: int | None = None):
        if not dest[0] == "c" and dest not in self.node_ids:
            raise ValueError("unknown destination:", dest)

        if msg_id is None:
            msg_id = self.last_msg_id
            self.last_msg_id += 1

        data = {
            "src": self.node_id,
            "dest": dest,
            "body": {
                k: v for k, v in dataclasses.asdict(body).items() if v is not None
            },
        }
        data["body"]["msg_id"] = msg_id

        x = json.dumps(data) + "\n"
        self.stdout.write(x.encode())
        await self.stdout.drain()

    async def communicate(
        self, res_cls: type[PayloadT], dest: str, body: Payload
    ) -> PayloadT:
        msg_id = self.last_msg_id
        self.last_msg_id += 1

        ev = asyncio.Event()
        self.receives_waiting[msg_id] = (ev, None)

        await self.send(dest, body, msg_id=msg_id)

        await self.receives_waiting[msg_id][0].wait()

        res_body = self.receives_waiting[msg_id][1]
        del self.receives_waiting[msg_id]

        return res_cls(**res_body)

    async def error(self, dest: str, code: MaelstormErrorCode, text: str | None = None):
        await self.send(dest, ErrorPayload(code=code.value, text=text))

    async def msg_init(self, msg: Message[InitPayload]) -> Reply[InitOkPayload]:
        return InitOkPayload()

    async def msg_error(self, msg: Message[ErrorPayload]) -> None:
        ...

    async def msg_echo(self, msg: Message[EchoPayload]) -> Reply[EchoOkPayload]:
        raise NotSupportedError()

    async def msg_echo_ok(self, msg: Message[EchoOkPayload]) -> None:
        raise NotSupportedError()

    async def msg_generate(
        self, msg: Message[GeneratePayload]
    ) -> Reply[GenerateOkPayload]:
        raise NotSupportedError()

    async def msg_generate_ok(self, msg: Message[GenerateOkPayload]) -> None:
        raise NotSupportedError()

    async def msg_topology(
        self, msg: Message[TopologyPayload]
    ) -> Reply[TopologyOkPayload]:
        raise NotSupportedError()

    async def msg_topology_ok(self, msg: Message[TopologyOkPayload]) -> None:
        raise NotSupportedError()

    async def msg_broadcast(
        self, msg: Message[BroadcastPayload]
    ) -> Reply[BroadcastOkPayload]:
        raise NotSupportedError()

    async def msg_broadcast_ok(self, msg: Message[BroadcastOkPayload]) -> None:
        raise NotSupportedError()

    async def msg_read(self, msg: Message[ReadPayload]) -> Reply[ReadOkPayload]:
        raise NotSupportedError()

    async def msg_read_ok(self, msg: Message[ReadOkPayload]) -> None:
        raise NotSupportedError()
