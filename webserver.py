#!/usr/bin/env python3


import json
import uuid
import socket
import asyncio
import logging
import webbrowser
from asyncio import CancelledError
from contextlib import suppress
from aiohttp import web

logger = logging.getLogger("webserver")

def find_host_ip():
	name = socket.gethostname()
	ip_addr = socket.gethostbyname(name)
	logger.debug("host %s, addr %s", name, ip_addr)
	return ip_addr


@web.middleware
async def verbose_middleware(request, handler):
    logger.debug(f">>> REQUEST: {request.method} {request.path}")
    try:
        response = await handler(request)
        logger.debug(f"<<< RESPONSE: {response.status} {request.path}")
        return response
    except Exception as e:
        logger.debug(f"!!! EXCEPTION: {e} {request.method} {request.path}")
        raise


class DglabConnection:
	def __init__(self, server, ws, id):
		self.server = server
		self.ws = ws
		self.id = id
		self.queue = None
		self.send_task = None

	def get_id(self):
		return self.id

	async def send_id(self):
		obj = {
			"type": "bind",
			"clientId": self.id,
			"targetId": "",
			"message": "targetId"
		}
		logger.debug("send_id %s", obj)
		await self.ws.send_json(obj)

	async def send(self, ty, msg):
		await self.queue.put((ty, msg))

	async def sender_task(self):
		while True:
			ty, msg = await self.queue.get()
			await self.server.send_msg(self.ws, ty, msg)
			self.queue.task_done()

	def start(self):
		assert(self.send_task is None)
		self.queue = asyncio.Queue(0x100)
		self.send_task = asyncio.create_task(self.sender_task())
		# self.send_task.add_done_callback(asyncio.Task.result)

	async def close(self):
		if self.send_task is not None:
			with suppress(CancelledError):
				self.send_task.cancel()


class DglabWebServer:
	# public
	def __init__(self, config = None):
		self.port = config and config.get("port") or 8080
		self.ip_addr = config and config.get("addr")
		if not self.ip_addr:
			self.ip_addr = find_host_ip()
		self.launch_browser = config.get("launch_browser")
		# self.app = web.Application(middlewares=[verbose_middleware])
		self.app = web.Application()

		self.client = None
		self.target = None
		self.conn_map = {}
		self.handler = None

	def run(self, func = None):
		async def index(request):
			return web.FileResponse('./client/index.html')
		self.app.router.add_get("/", index)
		self.app.router.add_get("/ws", self.websocket_handler)
		self.app.router.add_get("/{uuid:[0-9a-fA-F]{32}}", self.websocket_uuid_handler)
		self.app.router.add_static("/", path="./client")
		async def handle_startup(app):
			if func:
				self.handler = await func()
			if self.launch_browser:
				self.startup_task = asyncio.create_task(self.open_url())

		self.app.on_startup.append(handle_startup)

		web.run_app(self.app, port = self.port)

	async def feed_control(self, data):
		if self.target:
			await self.target.send("msg", data)

	async def feed_log(self, data):
		if self.client:
			await self.client.send("heartbeat", data)

	# private
	async def open_url(self):
		await asyncio.sleep(3)
		webbrowser.open("http://%s:%d" % (self.ip_addr, self.port), new = 1, autoraise = False)

	async def send_msg(self, ws, ty, msg):
		obj = {
			"type": ty,
			"clientId": self.client and self.client.get_id() or "",
			"targetId": self.target and self.target.get_id() or "",
			"message": msg,
		}
		logger.debug("send_msg %s", obj)
		await ws.send_json(obj)

	async def websocket_uuid_handler(self, request):
		uuid = request.path.lstrip('/')
		if uuid in self.conn_map:
			return await self.websocket_handler(request)
		else:
			raise web.HTTPForbidden()

	async def websocket_handler(self, request):
		ws = web.WebSocketResponse()
		await ws.prepare(request)

		id = uuid.uuid4().hex
		conn = DglabConnection(self, ws, id)
		logger.info("new client %s", id)
		await conn.send_id()

		self.conn_map[id] = conn
		logger.debug("client count %d", len(self.conn_map))

		try:
			while True:
				msg = await ws.receive_json()
				logger.debug("recv %s", msg)
				if msg.get("type", "") == "bind":
					client_id = msg.get("clientId", "")
					target_id = msg.get("targetId", "")

					if self.client or self.target or target_id != id:
						raise RuntimeError("invalid bind %s %s" % (client_id, target_id))

					self.client = self.conn_map.pop(client_id)
					self.target = self.conn_map.pop(target_id)
					assert(self.target == conn)
					logger.info("bind %s %s", client_id, target_id)
					self.client.start()
					self.target.start()

					await self.target.send("bind", "200")
					await self.client.send("bind", "200")

					await self.handle_device(ws)
					break
		except Exception as e:
			logger.error("exception on %s: %s", id, str(e))
		finally:
			self.conn_map.pop(id, None)
			logger.info("del client %s", id)
			await conn.close()

		if conn == self.target:
			if self.client:
				await self.client.send("break", "209")
			self.target = None

		elif conn == self.client:
			if self.target:
				await self.target.send("break", "209")
				await asyncio.sleep(1)
			self.client = None

		return ws

	async def handle_heartbeat(self):
		while True:
			await asyncio.sleep(25)
			await self.client.send("heartbeat", "")
			await self.target.send("heartbeat", "")

	async def handle_device(self, ws):
		heartbeat_task = asyncio.create_task(self.handle_heartbeat())
		try:
			while True:
				obj = await ws.receive_json()
				logger.debug("recv %s", obj)
				if obj.get("type", "") == "msg":
					msg = obj.get("message", "")
					await self.client.send("msg", msg)
					if callable(self.handler):
						try:
							await self.handler(msg)
						except Exception as e:
							logger.error("exception in handler: %s", str(e))
		finally:
			with suppress(CancelledError):
				heartbeat_task.cancel()


if __name__ == "__main__":
	server = DglabWebServer()
	server.run()